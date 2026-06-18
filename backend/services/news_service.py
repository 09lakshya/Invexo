import yfinance as yf
from datetime import datetime
from curl_cffi.requests import Session as curl_Session
from services.ticker_utils import ttl_cache
from services.logger import get_logger

logger = get_logger("news_service")

_yf_session = curl_Session(impersonate="chrome120")

@ttl_cache(maxsize=100, ttl=1800)
def get_stock_news(symbol: str):
    try:
        stock = yf.Ticker(symbol, session=_yf_session)
        try:
            news_data = stock.news
        except Exception:
            return []

        if not news_data or not isinstance(news_data, list):
            return []

        result = []
        for item in news_data[:6]:
            if not isinstance(item, dict):
                continue
            content = item.get("content") or {}
            title = item.get("title") or content.get("title") or ""
            if not title:
                continue
            
            ts = item.get("providerPublishTime")
            if not ts:
                pub_date = content.get("pubDate")
                if pub_date:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(pub_date[:10], "%Y-%m-%d")
                        ts = dt.timestamp()
                    except Exception:
                        ts = 0
            
            try:
                if ts:
                    date_str = datetime.fromtimestamp(ts).strftime("%d %b %Y")
                else:
                    date_str = "Recent"
            except Exception:
                date_str = "Recent"
                
            link = item.get("link")
            if not link:
                click = content.get("clickThroughUrl") or {}
                link = click.get("url", "#")
                
            publisher = item.get("publisher")
            if not publisher:
                prov = content.get("provider") or {}
                publisher = prov.get("displayName", "")

            result.append({
                "title": title,
                "link": link,
                "publisher": publisher,
                "date": date_str,
            })
        return result

    except Exception as e:
        logger.error(f"News Error for {symbol}: {e}")
        return []