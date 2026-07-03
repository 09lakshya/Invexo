from pydantic import BaseModel, EmailStr, Field
from typing import Literal


class SupportTicketInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Name of the person contacting support")
    email: EmailStr
    category: Literal["general", "bug", "feature", "account"] = "general"
    subject: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=5000)
