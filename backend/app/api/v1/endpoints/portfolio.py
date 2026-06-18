from fastapi import APIRouter, Depends, HTTPException, Request
from app.schemas.portfolio import HoldingCreate, HoldingResponse
from app.services.portfolio.portfolio_service import PortfolioService
from app.api.v1.dependencies import get_current_user, require_role
from app.core.limiter import limiter

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

@router.get("", response_model=list[HoldingResponse])
def handle_get_portfolio(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    return PortfolioService.get_portfolio(user_id)

@router.get("/analytics")
def handle_get_portfolio_analytics(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    return PortfolioService.get_portfolio_analytics(user_id)

@router.post("/add", response_model=dict)
@limiter.limit("15/minute")
def handle_add_holding(
    payload: HoldingCreate, 
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    user_id = str(current_user["id"])
    holding_id = PortfolioService.add_holding(
        user_id=user_id,
        symbol=payload.symbol,
        company_name=payload.company_name or "",
        quantity=payload.quantity,
        buy_price=payload.buy_price
    )
    if holding_id is None:
        raise HTTPException(status_code=500, detail="Failed to add stock holding")
    return {"id": holding_id, "success": True, "message": "Holding added successfully."}

@router.delete("/remove/{holding_id}", response_model=dict)
def handle_remove_holding(holding_id: int, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    success = PortfolioService.remove_holding(holding_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Holding not found or unauthorized to delete")
    return {"success": True, "message": "Holding removed successfully."}
