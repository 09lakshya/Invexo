from pydantic import BaseModel, Field
from typing import Optional


class CopilotHistoryTurn(BaseModel):
    sender: str = Field(..., description="'user' or 'copilot'")
    text: str = Field("", description="Message text")


class CopilotChatInput(BaseModel):
    message: str = Field(..., min_length=1, description="Message text cannot be empty")
    history: Optional[list[CopilotHistoryTurn]] = Field(
        default=None, description="Recent prior conversation turns for context"
    )
