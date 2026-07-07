from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.api.v1.dependencies import get_current_user
from app.repositories.signal_alert_repository import SignalAlertRepository
from app.schemas.signal_alert import (
    SignalSubscriptionCreate,
    SignalSubscriptionResponse,
    SignalNotificationList,
)

router = APIRouter(prefix="/signal-alerts", tags=["Signal Alerts"])


# ── Subscriptions ─────────────────────────────────────────────────────────
@router.post("/subscriptions", response_model=dict)
def subscribe(
    payload: SignalSubscriptionCreate,
    current_user: dict = Depends(get_current_user),
):
    sub_id = SignalAlertRepository.create_subscription(
        current_user["id"], payload.symbol, payload.min_confidence
    )
    if sub_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create signal alert subscription",
        )
    return {
        "success": True,
        "subscription_id": sub_id,
        "message": f"You'll be notified on buy/sell signals for {payload.symbol.upper()}",
    }


@router.get("/subscriptions", response_model=list[SignalSubscriptionResponse])
def list_subscriptions(current_user: dict = Depends(get_current_user)):
    return SignalAlertRepository.get_user_subscriptions(current_user["id"])


@router.delete("/subscriptions/{subscription_id}", response_model=dict)
def unsubscribe(subscription_id: int, current_user: dict = Depends(get_current_user)):
    success = SignalAlertRepository.delete_subscription(current_user["id"], subscription_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found or does not belong to you",
        )
    return {"success": True, "message": "Signal alert subscription removed"}


@router.delete("/subscriptions/by-symbol/{symbol}", response_model=dict)
def unsubscribe_by_symbol(symbol: str, current_user: dict = Depends(get_current_user)):
    success = SignalAlertRepository.delete_subscription_by_symbol(current_user["id"], symbol)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No signal alert subscription for that symbol",
        )
    return {"success": True, "message": "Signal alert subscription removed"}


# ── Notifications (in-app feed) ────────────────────────────────────────────
@router.get("/notifications", response_model=SignalNotificationList)
def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    notifications = SignalAlertRepository.get_user_notifications(current_user["id"], limit, offset)
    unread = SignalAlertRepository.count_unread(current_user["id"])
    return {
        "unread_count": unread,
        "count": len(notifications),
        "notifications": notifications,
    }


@router.get("/notifications/unread-count", response_model=dict)
def unread_count(current_user: dict = Depends(get_current_user)):
    return {"unread_count": SignalAlertRepository.count_unread(current_user["id"])}


@router.post("/notifications/{notification_id}/read", response_model=dict)
def mark_notification_read(notification_id: int, current_user: dict = Depends(get_current_user)):
    success = SignalAlertRepository.mark_read(current_user["id"], notification_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or does not belong to you",
        )
    return {"success": True}


@router.post("/notifications/read-all", response_model=dict)
def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    n = SignalAlertRepository.mark_all_read(current_user["id"])
    return {"success": True, "marked_read": n}
