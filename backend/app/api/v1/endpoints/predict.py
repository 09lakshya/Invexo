from fastapi import APIRouter, HTTPException, Depends, Request
from app.services.market.market_service import MarketService
from app.services.ai.prediction_service import PredictionService
from app.api.v1.dependencies import require_role
from app.core.limiter import limiter

router = APIRouter(prefix="/predict", tags=["Predict"])

@router.get("/daily-picks")
def get_daily_recommendations():
    picks = MarketService.get_daily_picks()
    if picks is None:
        return {"status": "updating", "message": "AI is analyzing the market...", "picks": []}
    return {"status": "ready", "picks": picks}

@router.get("/{symbol}")
@limiter.limit("15/minute")
def get_prediction(
    request: Request,
    symbol: str,
    current_user: dict = Depends(require_role(["user", "premium", "admin"]))
):
    res = PredictionService.predict_stock(symbol)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res
