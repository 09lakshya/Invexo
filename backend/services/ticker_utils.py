import hashlib
import json
import time
from functools import wraps
import yfinance as yf
from curl_cffi.requests import Session as curl_Session
from services.redis_client import redis_client

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
            df = yf.Ticker(candidate, session=_yf_session).history(period="5d")
            df = df.dropna(subset=["Close"])
            if not df.empty:
                return candidate
        except Exception:
            continue
    return symbol
