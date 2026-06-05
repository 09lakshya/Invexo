from fastapi import APIRouter
from services.news_service import get_stock_news
from services.general_news_service import get_general_news, search_general_news, suggest_general_news

router = APIRouter(prefix="/news")

def _ticker(symbol: str) -> str:
    if symbol == "NIFTY50":  return "^NSEI"
    if symbol == "SENSEX":   return "^BSESN"
    if symbol.endswith(".NS"):
        return symbol
    return symbol + ".NS"

@router.get("/general")
def general_news():
    return get_general_news()

@router.get("/general/search")
def search_news(q: str = ""):
    return search_general_news(q)

@router.get("/general/suggest")
def suggest_news(q: str = ""):
    return suggest_general_news(q)

@router.get("/{symbol}")
def stock_news(symbol: str):
    return get_stock_news(_ticker(symbol))
