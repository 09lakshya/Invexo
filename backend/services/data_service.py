import yfinance as yf
from services.ticker_utils import _yf_session, ttl_cache, _ticker_candidates

# =========================
# 📊 CURRENT PRICE FUNCTION
# =========================
@ttl_cache(maxsize=100, ttl=60)
def get_stock_price(symbol: str):
    for ticker_symbol in _ticker_candidates(symbol):
        try:
            stock = yf.Ticker(ticker_symbol, session=_yf_session)
            df = stock.history(period="2d")

            if df.empty:
                continue

            df = df.dropna(subset=["Close"])
            if df.empty:
                continue

            return float(df["Close"].iloc[-1])
        except Exception:
            continue
    return 0


# =========================
# 📈 HISTORY FUNCTION
# =========================
@ttl_cache(maxsize=100, ttl=300)
def get_history(symbol: str, period: str = "1mo"):
    for ticker_symbol in _ticker_candidates(symbol):
        try:
            stock = yf.Ticker(ticker_symbol, session=_yf_session)

            if period == "1d":
                # Intraday 5-minute data for the whole day
                df = stock.history(period="1d", interval="5m")
                if df.empty:
                    continue
            elif period == "5d":
                # Intraday 15-minute data for 5 days
                df = stock.history(period="5d", interval="15m")
                if df.empty:
                    continue
            else:
                # Daily data for 1mo and beyond
                df = stock.history(period=period, interval="1d")
                if df.empty:
                    continue

            df = df.dropna(subset=["Close"])
            if df.empty:
                continue

            df = df.reset_index()
            # yfinance returns 'Datetime' for intraday and 'Date' for daily
            date_col = "Datetime" if "Datetime" in df.columns else "Date"

            df = df[[date_col, "Open", "High", "Low", "Close"]]
            df = df.rename(columns={date_col: "Date"})

            df["Date"] = df["Date"].astype(str)
            df["Open"] = df["Open"].astype(float)
            df["High"] = df["High"].astype(float)
            df["Low"] = df["Low"].astype(float)
            df["Close"] = df["Close"].astype(float)

            return df.to_dict(orient="records")
        except Exception:
            continue

    return []
