from pydantic import BaseModel, Field
from typing import Optional

class AlertCreate(BaseModel):
    symbol: str = Field(..., min_length=1, description="Stock ticker symbol is required")
    target_price: float = Field(..., gt=0, description="Target price must be greater than 0")
    condition: str = Field(..., pattern="^(above|below)$", description="Condition must be 'above' or 'below'")

class AlertResponse(BaseModel):
    id: int
    user_id: int
    symbol: str
    target_price: float
    condition: str
    is_active: int
    created_at: str
    triggered_at: Optional[str] = None

    class Config:
        from_attributes = True
