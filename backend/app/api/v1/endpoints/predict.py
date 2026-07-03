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

@router.get("/daily-picks/stats")
def get_daily_picks_stats(days: int = 90):
    """Measured, realized accuracy of past Daily Edge picks."""
    from app.repositories.picks_repository import PicksRepository
    from app.services.ai.ranker_service import get_ranker_meta
    days = max(7, min(days, 365))
    stats = PicksRepository.get_accuracy_stats(days)
    meta = get_ranker_meta() or {}
    return {
        "realized": stats,
        "model": {
            "trained_at": meta.get("trained_at"),
            "universe_size": meta.get("symbols"),
            "walk_forward": meta.get("metrics", {}),
        },
    }

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
