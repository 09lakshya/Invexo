from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Optional
from app.schemas.support import SupportTicketInput
from app.services.support.support_service import SupportService
from app.repositories.support_repository import SupportRepository
from app.api.v1.dependencies import get_optional_user
from app.api.v1.endpoints.admin import verify_admin_token
from app.core.limiter import limiter

router = APIRouter(prefix="/support", tags=["Support"])


@router.post("/contact")
@limiter.limit("5/minute")
def handle_support_contact(
    payload: SupportTicketInput,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    try:
        stored = SupportService.submit_ticket(
            name=payload.name.strip(),
            email=payload.email,
            category=payload.category,
            subject=payload.subject.strip(),
            message=payload.message.strip(),
            user_id=current_user["id"] if current_user else None,
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Support service is temporarily unavailable. Please email us directly.",
        )

    if not stored:
        raise HTTPException(
            status_code=502,
            detail="We couldn't record your message right now. Please try again shortly.",
        )

    return {"message": "Your message has been sent. We'll get back to you soon!"}


@router.get("/tickets")
@limiter.limit("30/minute")
def list_support_tickets(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    token: str = Depends(verify_admin_token),
):
    """List stored support tickets. Protected by the X-Admin-Token header."""
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    return {"tickets": SupportRepository.list_tickets(limit=limit, offset=offset)}
