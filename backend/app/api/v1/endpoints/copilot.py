from fastapi import APIRouter, Depends
from app.api.v1.dependencies import get_current_user
from app.schemas.copilot import CopilotChatInput
from app.services.ai.copilot_service import CopilotService

router = APIRouter(prefix="/copilot", tags=["AI Copilot"])

@router.post("/chat")
def copilot_chat(
    payload: CopilotChatInput,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    response_text = CopilotService.get_copilot_response(user_id, payload.message)
    return {"response": response_text}
