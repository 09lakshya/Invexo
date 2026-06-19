import yfinance as yf
import pandas as pd
import numpy as np
from app.services.market.ticker_utils import ttl_cache, _working_ticker, _yf_session
from app.utils.logger import get_logger
from .ai_service import _safe_float

logger = get_logger("fundamentals_service")

@ttl_cache(maxsize=100, ttl=86400)
def get_fundamental_data(symbol: str) -> dict:
    try:
        stock = yf.Ticker(_working_ticker(symbol), session=_yf_session)
        info = stock.get_info() or {}
        fast_info = getattr(stock, "fast_info", {}) or {}
        
        fundamentals = {
            "pe_ratio": _safe_float(info.get("trailingPE")),
            "pb_ratio": _safe_float(info.get("priceToBook")),
            "dividend_yield": _safe_float(info.get("dividendYield"), 0),
            "earnings_growth": _safe_float(info.get("earningsGrowth"), 0),
            "revenue_growth": _safe_float(info.get("revenueGrowth"), 0),
            "profit_margin": _safe_float(info.get("profitMargins"), 0),
            "debt_to_equity": _safe_float(info.get("debtToEquity")),
            "roa": _safe_float(info.get("returnOnAssets"), 0),
            "roe": _safe_float(info.get("returnOnEquity"), 0),
            "market_cap": _safe_float(info.get("marketCap") or fast_info.get("market_cap"), 0),
            "data_points": 0,
        }

        fundamentals["data_points"] = sum(
            1 for key in [
                "pe_ratio", "pb_ratio", "dividend_yield", "earnings_growth",
                "revenue_growth", "profit_margin", "debt_to_equity", "roa",
                "roe", "market_cap"
            ]
            if fundamentals.get(key) not in (None, 0)
        )
        return fundamentals
    except Exception as e:
        logger.error(f"Fundamental data error: {e}")
        return {}

def calculate_fundamental_score(fundamentals: dict) -> float | None:
    score = 50
    factors = 0
    
    try:
        pe = fundamentals.get("pe_ratio")
        if pe and pe > 0:
            if pe < 15:
                score += 10
            elif pe > 30:
                score -= 5
            factors += 1
        
        eg = fundamentals.get("earnings_growth", 0)
        if eg and eg > 0:
            score += min(eg * 10, 15)
            factors += 1
        elif eg and eg < 0:
            score -= min(abs(eg) * 10, 10)
            factors += 1
        
        rg = fundamentals.get("revenue_growth", 0)
        if rg and rg > 0:
            score += min(rg * 5, 10)
            factors += 1
        
        roe = fundamentals.get("roe", 0)
        if roe and roe > 0.15:
            score += 8
            factors += 1
        elif roe and roe < 0:
            score -= 8
            factors += 1
        
        dte = fundamentals.get("debt_to_equity")
        if dte and dte > 2:
            score -= 5
            factors += 1
        elif dte and dte < 1:
            score += 5
            factors += 1
        
        dy = fundamentals.get("dividend_yield", 0)
        if dy and dy > 0.02:
            score += 5
            factors += 1
    except Exception as e:
        logger.error(f"Fundamental scoring error: {e}")
    
    if factors == 0:
        return None

    reliability = min(1, factors / 4)
    score = 50 + ((score - 50) * reliability)
    return max(0, min(100, score))

def calculate_technical_quality_score(close: pd.Series, volume: pd.Series) -> float:
    returns = close.pct_change().dropna()
    if returns.empty:
        return 50

    momentum_3m = close.iloc[-1] / close.iloc[-min(63, len(close))] - 1
    momentum_1m = close.iloc[-1] / close.iloc[-min(22, len(close))] - 1
    volatility = returns.tail(60).std() * np.sqrt(252)
    drawdown = close.iloc[-1] / close.tail(min(126, len(close))).max() - 1
    avg_volume = volume.tail(min(20, len(volume))).mean()

    score = 50
    score += max(-18, min(18, momentum_3m * 80))
    score += max(-10, min(10, momentum_1m * 70))
    score -= max(0, min(12, (volatility - 0.25) * 25))
    score += max(-8, min(4, drawdown * 20))
    if avg_volume and avg_volume > 0:
        score += 3

    return max(20, min(80, score))
