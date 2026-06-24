from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, Request
from typing import Optional
import asyncio
import io
import os
import json
import gc
from contextlib import redirect_stdout, redirect_stderr
from app.services.market.data_service import DataService
from app.services.market.news_service import NewsService
from app.services.market.general_news_service import GeneralNewsService
from app.services.ai.prediction_service import PredictionService
from app.services.ai.backtesting_service import BacktestingService
from app.core.security import verify_access_token
from app.core.redis import redis_client
from app.core.limiter import limiter
from app.api.v1.dependencies import get_current_user, require_role
from app.utils.logger import get_logger

logger = get_logger("market_endpoints")

router = APIRouter(prefix="/market", tags=["Market Data"])

NIFTY50_SYMBOLS = [
    "NIFTY50", "SENSEX",
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HINDALCO",
    "HINDUNILVR", "ICICIBANK", "INDIGO", "INFY", "ITC",
    "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT", "M&M",
    "MARUTI", "MAXHEALTH", "NESTLEIND", "NTPC", "ONGC", "POWERGRID",
    "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN",
    "SUNPHARMA", "TCS", "TATACONSUM", "TMPV", "TATASTEEL",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO"
]

def get_ticker(symbol: str) -> str:
    symbol_upper = symbol.upper().strip()
    if symbol_upper == "NIFTY50":
        return "^NSEI"
    elif symbol_upper == "SENSEX":
        return "^BSESN"
    elif symbol_upper == "TATAMOTORS":
        return "TATAMOTORS.BO"
    elif symbol_upper.endswith(".NS"):
        return symbol_upper
    else:
        return symbol_upper + ".NS"

GLOBAL_CACHE = {
    "NIFTY50": {"price": 0, "change": 0, "percent": 0},
    "SENSEX": {"price": 0, "change": 0, "percent": 0}
}

try:
    cached_val = redis_client.get("market:global_cache")
    if cached_val:
        cached_data = json.loads(cached_val)
        if isinstance(cached_data, dict) and len(cached_data) > 0:
            GLOBAL_CACHE.update(cached_data)
except Exception as e:
    logger.error(f"Error loading market cache from Redis: {e}")

_background_task = None
_active_local_connections = set()

# ==========================================
# 🔄 REDIS PUB/SUB WEBSOCKET DISTRIBUTED SCALING
# ==========================================

async def update_market_cache_loop():
    """Background task to download market ticks and publish them to Redis Pub/Sub."""
    global GLOBAL_CACHE
    tickers_map = {get_ticker(s): s for s in NIFTY50_SYMBOLS}
    ticker_string = " ".join(tickers_map.keys())
    
    while True:
        try:
            # Distributed Lock: Only one worker node should fetch from Yahoo Finance to avoid rate limiting
            lock_key = "lock:market_fetcher"
            # Attempt to set lock for 12 seconds
            if redis_client.enabled and redis_client.client:
                is_locked = redis_client.client.set(lock_key, "locked", ex=12, nx=True)
                if not is_locked:
                    # Some other node is updating the cache, sleep and continue
                    await asyncio.sleep(15)
                    continue
            
            import yfinance as yf
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                df = yf.download(ticker_string, period="5d", interval="1d", progress=False)
            
            new_data = {}
            if "Close" in df:
                close_df = df["Close"]
                for ticker, sym in tickers_map.items():
                    try:
                        if hasattr(close_df, "columns") and ticker in close_df.columns:
                            close_series = close_df[ticker].dropna()
                        elif isinstance(close_df, dict) and ticker in close_df:
                            close_series = close_df[ticker].dropna()
                        elif isinstance(close_df, type(df["Close"])) and len(tickers_map) == 1:
                            close_series = close_df.dropna()
                        else:
                            continue
                            
                        if len(close_series) < 2:
                            continue
                            
                        price = float(close_series.iloc[-1])
                        prev_close = float(close_series.iloc[-2])
                        change = price - prev_close
                        percent = (change / prev_close * 100) if prev_close != 0 else 0
                        
                        new_data[sym] = {
                            "price": round(price, 2),
                            "change": round(change, 2),
                            "percent": round(percent, 2)
                        }
                    except Exception as ex:
                        logger.error(f"Error parsing {sym}: {ex}")

            new_data.setdefault("NIFTY50", GLOBAL_CACHE.get("NIFTY50", {"price": 0, "change": 0, "percent": 0}))
            new_data.setdefault("SENSEX", GLOBAL_CACHE.get("SENSEX", {"price": 0, "change": 0, "percent": 0}))

            if new_data:
                GLOBAL_CACHE.update(new_data)
                if redis_client.enabled and redis_client.client:
                    redis_client.client.set("market:global_cache", json.dumps(GLOBAL_CACHE))
                    # Publish ticks to all connected workers
                    redis_client.client.publish("market:ticks", json.dumps(GLOBAL_CACHE))
                else:
                    # Broadcast directly to local connected clients if Redis is disabled
                    for connection in list(_active_local_connections):
                        try:
                            asyncio.create_task(connection.send_json(GLOBAL_CACHE))
                        except Exception:
                            _active_local_connections.discard(connection)
                
            if 'df' in locals():
                del df
            gc.collect()
        except Exception as e:
            logger.error(f"Failed to bulk fetch market data: {e}")
            
        await asyncio.sleep(15)

async def redis_listener():
    """Subscribes to Redis Pub/Sub channel and broadcasts to local WebSocket clients."""
    if not redis_client.enabled or not redis_client.client:
        return
        
    pubsub = redis_client.client.pubsub()
    pubsub.subscribe("market:ticks")
    
    try:
        while True:
            # Non-blocking check for messages from Redis Pub/Sub channel
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = json.loads(message["data"])
                GLOBAL_CACHE.update(data)
                # Broadcast to local connected connections
                for connection in list(_active_local_connections):
                    try:
                        await connection.send_json(GLOBAL_CACHE)
                    except Exception:
                        _active_local_connections.discard(connection)
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Redis Pub/Sub listener disconnected: {e}")
        try:
            pubsub.unsubscribe("market:ticks")
        except Exception:
            pass

# ==========================================
# ⚡ SECURED & SCALABLE WEBSOCKET ENDPOINT
# ==========================================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    global _background_task
    
    # 1. Heartbeat Connection Security Checks
    # Authenticate via Token query parameter (since standard headers are not accessible via standard WSS browser handshakes)
    if not token:
        await websocket.close(code=4001, reason="Authentication token is required")
        return
        
    user_id = verify_access_token(token)
    if user_id is None:
        await websocket.close(code=4002, reason="Invalid, expired or revoked authentication token")
        return

    await websocket.accept()
    
    # 2. Connection Limit Safety checks (max 100 concurrent clients per node to avoid memory leaks)
    if len(_active_local_connections) >= 100:
        await websocket.close(code=4003, reason="Server capacity limit reached. Try connecting later.")
        return
        
    _active_local_connections.add(websocket)
    
    # Start the global caching fetcher loop if it is not running
    if _background_task is None:
        _background_task = asyncio.create_task(update_market_cache_loop())
        # Start the Redis pub/sub listener as well
        asyncio.create_task(redis_listener())

    # Send the current cache immediately
    await websocket.send_json(GLOBAL_CACHE)
    
    # Heartbeat ping task
    async def send_heartbeat_pings():
        try:
            while websocket in _active_local_connections:
                await websocket.send_json({"type": "ping"})
                await asyncio.sleep(20)  # Ping every 20 seconds
        except Exception:
            pass

    ping_task = asyncio.create_task(send_heartbeat_pings())
    
    try:
        while True:
            # Listen to messages or pongs
            data = await websocket.receive_text()
            # If clients send messages, we can validate or drop them
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _active_local_connections.discard(websocket)
        ping_task.cancel()

# ==========================================
# 📊 API ROUTERS
# ==========================================

@router.get("/indices")
def get_indices():
    """Retrieve benchmark Nifty 50 and Sensex index statistics."""
    # Sync with latest Redis cache
    try:
        cached_val = redis_client.get("market:global_cache")
        if cached_val:
            cached_data = json.loads(cached_val)
            GLOBAL_CACHE.update(cached_data)
    except Exception:
        pass
    return {
        "NIFTY50": GLOBAL_CACHE.get("NIFTY50", {"price": 0, "change": 0, "percent": 0}),
        "SENSEX": GLOBAL_CACHE.get("SENSEX", {"price": 0, "change": 0, "percent": 0})
    }

@router.get("/news")
@limiter.limit("20/minute")
def get_market_news(request: Request):
    """Fetch general markets and companies news."""
    return GeneralNewsService.get_general_news()

@router.get("/news/stock/{symbol}")
def get_stock_news(symbol: str):
    """Fetch news headlines specifically for a stock symbol."""
    return NewsService.get_stock_news(symbol)

@router.get("/news/search")
def search_news(query: str = Query(..., min_length=1)):
    """Search for business articles matching a query."""
    return GeneralNewsService.search_general_news(query)

@router.get("/news/suggest")
def suggest_news(query: str = Query(..., min_length=1)):
    """Retrieve auto-complete search news query recommendations."""
    return GeneralNewsService.suggest_general_news(query)

@router.get("/predict/{symbol}")
@limiter.limit("15/minute")
def get_prediction(
    request: Request,
    symbol: str,
    # Enforce Premium User or Admin roles to access prediction analytics
    current_user: dict = Depends(require_role(["premium", "admin"]))
):
    """Execute AI prediction models on a stock symbol."""
    res = PredictionService.predict_stock(symbol)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.get("/backtest/{symbol}")
@limiter.limit("10/minute")
def run_backtest(
    request: Request,
    symbol: str,
    strategy: str = Query("MA", description="MA (Moving Average Crossover) or RSI"),
    period: str = Query("2y", description="Time period (1y, 2y, 5y)"),
    current_user: dict = Depends(require_role(["premium", "admin"]))
):
    """Evaluate financial performance using historical backtesting strategies."""
    res = BacktestingService.run_backtest(symbol, strategy, period)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.get("/{symbol}")
def get_stock_price(symbol: str):
    """Get the current live trading price of a stock symbol."""
    ticker = get_ticker(symbol)
    price = DataService.get_stock_price(ticker)
    return {
        "symbol": symbol,
        "price": price
    }

@router.get("/{symbol}/history")
def get_stock_history(symbol: str, period: str = Query("1mo", description="Historical period (1d, 5d, 1mo, 6mo, 1y)")):
    """Retrieve historical price candles for charts."""
    ticker = get_ticker(symbol)
    return DataService.get_history(ticker, period)
