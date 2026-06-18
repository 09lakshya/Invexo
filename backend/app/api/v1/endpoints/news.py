from fastapi import APIRouter, Query
from app.services.market.general_news_service import GeneralNewsService
from app.services.market.news_service import NewsService

router = APIRouter(prefix="/news", tags=["News"])

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

@router.get("/general")
def general_news():
    return GeneralNewsService.get_general_news()

@router.get("/general/search")
def search_news(q: str = Query("")):
    return GeneralNewsService.search_general_news(q)

@router.get("/general/suggest")
def suggest_news(q: str = Query("")):
    return GeneralNewsService.suggest_general_news(q)

@router.get("/{symbol}")
def stock_news(symbol: str):
    ticker = get_ticker(symbol)
    return NewsService.get_stock_news(ticker)
