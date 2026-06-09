from fastapi import APIRouter

router = APIRouter(prefix="/predict")

@router.get("/daily-picks")
def get_daily_recommendations():
    from services.daily_picks_service import get_daily_picks
    picks = get_daily_picks()
    if picks is None:
        return {"status": "updating", "message": "AI is analyzing the market...", "picks": []}
    return {"status": "ready", "picks": picks}

@router.get("/{symbol}")
def get_prediction(symbol: str):
    from services.ai_service import predict_stock
    return predict_stock(symbol)