import requests
from datetime import datetime
import pytz
from app.services.market.ticker_utils import _yf_session, ttl_cache, _ticker_candidates

class DataService:
    @staticmethod
    @ttl_cache(maxsize=100, ttl=60)
    def get_stock_price(symbol: str) -> float:
        import yfinance as yf
        for ticker_symbol in _ticker_candidates(symbol):
            try:
                stock = yf.Ticker(ticker_symbol)
                last_price = stock.fast_info.get("lastPrice")
                if last_price is not None and not __import__("math").isnan(last_price):
                    return float(last_price)
                    
                df = stock.history(period="1d", interval="5m")
                if df.empty:
                    continue

                df = df.dropna(subset=["Close"])
                if df.empty:
                    continue

                return float(df["Close"].iloc[-1])
            except Exception:
                continue
        return 0.0

    @staticmethod
    @ttl_cache(maxsize=100, ttl=300)
    def get_history(symbol: str, period: str = "1mo") -> list[dict]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        if period == "1d":
            range_val = "1d"
            interval_val = "5m"
        elif period == "5d":
            range_val = "5d"
            interval_val = "15m"
        else:
            range_val = period
            interval_val = "1d"

        for ticker_symbol in _ticker_candidates(symbol):
            try:
                url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?range={range_val}&interval={interval_val}"
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code != 200:
                    continue

                data = res.json()
                result = data.get("chart", {}).get("result", [])
                if not result:
                    continue

                result_data = result[0]
                timestamps = result_data.get("timestamp", [])
                indicators = result_data.get("indicators", {}).get("quote", [{}])[0]

                opens = indicators.get("open", [])
                highs = indicators.get("high", [])
                lows = indicators.get("low", [])
                closes = indicators.get("close", [])

                tz_name = result_data.get("meta", {}).get("exchangeTimezoneName", "UTC")
                try:
                    tz = pytz.timezone(tz_name)
                except Exception:
                    tz = pytz.UTC

                records = []
                for i in range(len(timestamps)):
                    ts = timestamps[i]
                    dt = datetime.fromtimestamp(ts, tz)

                    if interval_val in ["5m", "15m"]:
                        date_str = dt.replace(microsecond=0).isoformat(sep=" ")
                    else:
                        date_str = dt.strftime("%Y-%m-%d")

                    open_val = opens[i]
                    high_val = highs[i]
                    low_val = lows[i]
                    close_val = closes[i]

                    if close_val is None:
                        continue

                    records.append({
                        "Date": date_str,
                        "Open": float(open_val) if open_val is not None else float(close_val),
                        "High": float(high_val) if high_val is not None else float(close_val),
                        "Low": float(low_val) if low_val is not None else float(close_val),
                        "Close": float(close_val)
                    })

                return records
            except Exception:
                continue

        return []
