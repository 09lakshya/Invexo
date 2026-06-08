from fastapi import APIRouter
from services.ai_service import predict_stock
from services.daily_picks_service import get_daily_picks

router = APIRouter(prefix="/predict")

@router.get("/daily-picks")
def get_daily_recommendations():
    picks = get_daily_picks()
    if picks is None:
        return {"status": "updating", "message": "AI is analyzing the market...", "picks": []}
    return {"status": "ready", "picks": picks}

@router.get("/{symbol}")
def get_prediction(symbol: str):
    return predict_stock(symbol)