from pydantic import BaseModel, Field
from typing import Optional

class WatchlistItemCreate(BaseModel):
    symbol: str = Field(..., min_length=1, description="Stock ticker symbol is required")

class WatchlistItemResponse(BaseModel):
    id: int
    user_id: int
    symbol: str
    created_at: str

    class Config:
        from_attributes = True
