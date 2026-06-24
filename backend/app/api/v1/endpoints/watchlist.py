from fastapi import APIRouter, Depends, HTTPException, status
from concurrent.futures import ThreadPoolExecutor
from app.api.v1.dependencies import get_current_user
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemResponse
from app.services.market.ticker_utils import _working_ticker, _yf_session
from app.services.market.advisor_service import AdvisorService, UNIVERSE
import yfinance as yf

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])

def fetch_watchlist_item_details(symbol: str):
    ticker_symbol = _working_ticker(symbol)
    meta = UNIVERSE.get(ticker_symbol, {})
    name = meta.get("name", symbol.upper())
    sector = meta.get("sector", "Other")
    
    signals = AdvisorService._fetch_signals(symbol)
    price = 0.0
    change = 0.0
    change_pct = 0.0
    trend = "BEARISH"
    rsi = 50.0
    
    if signals:
        price = signals.get("current_price", 0.0)
        trend = signals.get("trend", "BEARISH")
        rsi = signals.get("rsi", 50.0)
        
        # Calculate daily change percentage from yfinance history
        try:
            df = yf.Ticker(ticker_symbol, session=_yf_session).history(period="5d", interval="1d")
            if not df.empty and len(df) >= 2:
                close = df["Close"]
                current_close = float(close.iloc[-1])
                prev_close = float(close.iloc[-2])
                change = round(current_close - prev_close, 2)
                change_pct = round(((current_close - prev_close) / prev_close) * 100, 2)
        except Exception:
            pass

    return {
        "symbol": symbol.upper().strip(),
        "name": name,
        "sector": sector,
        "current_price": price,
        "change": change,
        "change_pct": change_pct,
        "trend": trend,
        "rsi": rsi
    }

@router.post("/", response_model=dict)
def add_to_watchlist(
    payload: WatchlistItemCreate,
    current_user: dict = Depends(get_current_user)
):
    symbol = payload.symbol.upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol cannot be empty")
        
    success = WatchlistRepository.add_to_watchlist(current_user["id"], symbol)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add to watchlist (possibly already added)"
        )
    return {"success": True, "message": f"{symbol} added to watchlist"}

@router.delete("/{symbol}", response_model=dict)
def remove_from_watchlist(
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    symbol = symbol.upper().strip()
    success = WatchlistRepository.remove_from_watchlist(current_user["id"], symbol)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{symbol} was not found in your watchlist"
        )
    return {"success": True, "message": f"{symbol} removed from watchlist"}

@router.get("/")
def get_watchlist(
    current_user: dict = Depends(get_current_user)
):
    items = WatchlistRepository.get_watchlist(current_user["id"])
    symbols = [item["symbol"] for item in items]
    
    # Fetch price and indicators details in parallel to speed up response times
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_watchlist_item_details, sym): sym for sym in symbols}
        for future in futures:
            try:
                results.append(future.result())
            except Exception:
                pass
                
    return results
