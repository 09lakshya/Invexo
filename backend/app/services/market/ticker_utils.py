import time
import hashlib
import json
from functools import wraps
import yfinance as yf
from curl_cffi.requests import Session as curl_Session
from app.core.redis import redis_client

_yf_session = curl_Session(impersonate="chrome120")

def ttl_cache(maxsize=100, ttl=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a unique key for the function and arguments
            args_str = f"{args}:{sorted(kwargs.items())}"
            key_hash = hashlib.md5(args_str.encode('utf-8')).hexdigest()
            redis_key = f"cache:{func.__module__}:{func.__name__}:{key_hash}"
            
            cached_val = redis_client.get(redis_key)
            if cached_val is not None:
                try:
                    return json.loads(cached_val)
                except Exception:
                    return cached_val
                    
            result = func(*args, **kwargs)
            try:
                redis_client.set(redis_key, json.dumps(result), ex=ttl)
            except Exception:
                try:
                    redis_client.set(redis_key, str(result), ex=ttl)
                except Exception:
                    pass
            return result
        return wrapper
    return decorator

YF_SYMBOL_OVERRIDES = {}

def _ticker_candidates(symbol: str):
    symbol_upper = symbol.upper().strip()
    if symbol_upper in YF_SYMBOL_OVERRIDES:
        yield YF_SYMBOL_OVERRIDES[symbol_upper]
        return
        
    # Standard NSE / BSE tickers format fallback (Prioritize for Indian stocks)
    if not symbol_upper.endswith(".NS") and not symbol_upper.endswith(".BO"):
        yield f"{symbol_upper}.NS"
        yield f"{symbol_upper}.BO"
        
    yield symbol_upper

@ttl_cache(maxsize=100, ttl=86400)
def _working_ticker(symbol: str) -> str:
    """Tries candidates and returns the first one that successfully returns metadata from yfinance."""
    for candidate in _ticker_candidates(symbol):
        try:
            ticker = yf.Ticker(candidate, session=_yf_session)
            # Fetch minimal info to check validity
            hist = ticker.history(period="1d")
            if not hist.empty:
                return candidate
        except Exception:
            continue
    # Default fallback to .NS
    return f"{symbol.upper()}.NS"
