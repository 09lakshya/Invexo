from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional
from pydantic import BaseModel
from app.services.market.advisor_service import AdvisorService
from app.services.calculator.calculator_service import CalculatorService
from app.api.v1.dependencies import get_current_user, require_role
from app.core.limiter import limiter

router = APIRouter(prefix="/advisor", tags=["AI Advisor"])

class AdvisorInput(BaseModel):
    goal: str
    duration: str
    risk: str
    budget: float
    investmentType: str = "one-time"
    investmentMonths: Optional[int] = None

class CalculatorInput(BaseModel):
    principal: float
    annual_rate: float
    years: int
    inflation_rate: float = 0.06

class PortfolioSummaryInput(BaseModel):
    stocks: list
    budget: float

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
    current_user: dict = Depends(require_role(["user", "premium", "admin"]))
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

@router.post("/recommend")
@limiter.limit("10/minute")
def recommend(
    request: Request,
    payload: AdvisorInput,
    current_user: dict = Depends(require_role(["user", "premium", "admin"]))
):
    if payload.budget <= 0:
        raise HTTPException(status_code=400, detail="Budget must be greater than 0")
        
    return AdvisorService.get_recommendations(
        goal=payload.goal,
        duration=payload.duration,
        risk=payload.risk,
        budget=payload.budget,
        investment_type=payload.investmentType,
        investment_months=payload.investmentMonths
    )

@router.post("/calculate")
def calculate(payload: CalculatorInput):
    """Calculate investment returns with inflation adjustment"""
    return CalculatorService.calculate_investment(
        principal=payload.principal,
        annual_rate=payload.annual_rate / 100,  # Convert percentage to decimal
        years=payload.years,
        inflation_rate=payload.inflation_rate / 100,
    )

@router.post("/portfolio-summary")
def portfolio_summary(payload: PortfolioSummaryInput):
    """Calculate portfolio-level metrics"""
    portfolio_metrics = CalculatorService.calculate_portfolio_metrics(payload.stocks, payload.budget)
    portfolio_returns = CalculatorService.estimate_returns(payload.stocks, years=3)
    
    return {
        "metrics": portfolio_metrics,
        "projections": portfolio_returns,
    }
