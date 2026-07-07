from pydantic import BaseModel, Field
from typing import Optional


class SignalSubscriptionCreate(BaseModel):
    symbol: str = Field(..., min_length=1, description="Stock ticker symbol is required")
    min_confidence: int = Field(
        60, ge=35, le=95,
        description="Only notify when the model's confidence is at least this (35–95)."
    )


class SignalSubscriptionResponse(BaseModel):
    id: int
    user_id: int
    symbol: str
    min_confidence: int
    is_active: int
    created_at: str

    class Config:
        from_attributes = True


class SignalNotificationResponse(BaseModel):
    id: int
    symbol: str
    action: str
    trend: Optional[str] = None
    confidence: Optional[int] = None
    price: Optional[float] = None
    message: Optional[str] = None
    source: Optional[str] = None
    is_read: int
    created_at: str

    class Config:
        from_attributes = True


class SignalNotificationList(BaseModel):
    unread_count: int
    count: int
    notifications: list[SignalNotificationResponse]
