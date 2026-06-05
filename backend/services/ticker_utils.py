import time
from functools import wraps
import yfinance as yf
from curl_cffi.requests import Session as curl_Session

_yf_session = curl_Session(impersonate="chrome120")

def ttl_cache(maxsize=100, ttl=300):
    def decorator(func):
        cache = {}
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            now = time.time()
            if key in cache:
                result, timestamp = cache[key]
                if now - timestamp < ttl:
                    return result
            result = func(*args, **kwargs)
            if len(cache) >= maxsize:
                cache.pop(next(iter(cache)))
            cache[key] = (result, now)
            return result
        return wrapper
    return decorator

YF_SYMBOL_OVERRIDES = {}

def _ticker_candidates(symbol: str):
    symbol = str(symbol).strip().upper()
    if symbol in YF_SYMBOL_OVERRIDES:
        override = YF_SYMBOL_OVERRIDES[symbol]
        if override.endswith(".BO"):
            base = override[:-3]
            return [override, f"{base}.NS"]
        if override.endswith(".NS"):
            base = override[:-3]
            return [override, f"{base}.BO"]
        return [override]
    if symbol.startswith("^"):
        return [symbol]
    if symbol.endswith(".NS"):
        base = symbol[:-3]
        return [symbol, f"{base}.BO"]
    if symbol.endswith(".BO"):
        base = symbol[:-3]
        return [symbol, f"{base}.NS"]
    return [f"{symbol}.NS", f"{symbol}.BO"]

@ttl_cache(maxsize=100, ttl=86400)
def _working_ticker(symbol: str):
    for candidate in _ticker_candidates(symbol):
        try:
            df = yf.Ticker(candidate).history(period="5d")
            df = df.dropna(subset=["Close"])
            if not df.empty:
                return candidate
        except Exception:
            continue
    return symbol
