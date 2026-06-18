from fastapi import APIRouter, Depends, HTTPException, status
from app.api.v1.dependencies import get_current_user
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertCreate, AlertResponse

router = APIRouter(prefix="/alerts", tags=["Smart Alerts"])

@router.post("/", response_model=dict)
def create_alert(
    payload: AlertCreate,
    current_user: dict = Depends(get_current_user)
):
    symbol = payload.symbol.upper().strip()
    condition = payload.condition.lower().strip()
    target_price = payload.target_price
    
    new_id = AlertRepository.create_alert(
        current_user["id"],
        symbol,
        target_price,
        condition
    )
    if new_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create smart price alert"
        )
    return {
        "success": True,
        "alert_id": new_id,
        "message": f"Alert set for {symbol} when price goes {condition} {target_price}"
    }

@router.get("/", response_model=list[AlertResponse])
def get_user_alerts(
    current_user: dict = Depends(get_current_user)
):
    return AlertRepository.get_user_alerts(current_user["id"])

@router.delete("/{alert_id}", response_model=dict)
def delete_alert(
    alert_id: int,
    current_user: dict = Depends(get_current_user)
):
    success = AlertRepository.delete_alert(current_user["id"], alert_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found or does not belong to you"
        )
    return {"success": True, "message": "Alert deleted successfully"}
