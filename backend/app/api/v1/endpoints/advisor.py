from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional
from app.services.market.advisor_service import AdvisorService
from app.api.v1.dependencies import get_current_user, require_role
from app.core.limiter import limiter

router = APIRouter(prefix="/advisor", tags=["AI Advisor"])

@router.get("/recommendations")
@limiter.limit("10/minute")
def handle_get_recommendations(
    request: Request,
    goal: str = Query("wealth", description="Investment goal (wealth, income, retirement, education, safety)"),
    duration: str = Query("medium", description="Horizon (short, medium, long)"),
    risk: str = Query("medium", description="Risk tolerance (low, medium, high)"),
    budget: float = Query(50000.0, description="Amount (₹)"),
    investment_type: str = Query("one-time", description="Sip or one-time"),
    investment_months: Optional[int] = Query(None, description="sip duration in months"),
    # Require Premium User or Admin roles to access AI advisor reports
    current_user: dict = Depends(require_role(["premium", "admin"]))
):
    if budget <= 0:
        raise HTTPException(status_code=400, detail="Budget must be greater than 0")
        
    return AdvisorService.get_recommendations(
        goal=goal,
        duration=duration,
        risk=risk,
        budget=budget,
        investment_type=investment_type,
        investment_months=investment_months
    )
