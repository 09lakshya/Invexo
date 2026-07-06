from pydantic import BaseModel, Field
from typing import Optional

class HoldingCreate(BaseModel):
    symbol: str = Field(..., min_length=1, description="Stock ticker symbol is required")
    company_name: Optional[str] = None
    quantity: float = Field(..., gt=0, description="Quantity must be greater than 0")
    buy_price: float = Field(..., gt=0, description="Buy price must be greater than 0")

class HoldingResponse(BaseModel):
    id: int
    user_id: str
    symbol: str
    company_name: Optional[str] = None
    quantity: float
    buy_price: float
    added_on: Optional[str] = None

    # Computed financials (attached by PortfolioService.get_portfolio)
    invested: Optional[float] = None
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None

    class Config:
        from_attributes = True
