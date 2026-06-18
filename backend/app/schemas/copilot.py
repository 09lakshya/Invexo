from pydantic import BaseModel, Field

class CopilotChatInput(BaseModel):
    message: str = Field(..., min_length=1, description="Message text cannot be empty")
