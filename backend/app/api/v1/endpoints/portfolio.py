from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from app.schemas.portfolio import HoldingCreate, HoldingResponse, ImportCommit
from app.services.portfolio.portfolio_service import PortfolioService
from app.api.v1.dependencies import get_current_user, require_role
from app.core.limiter import limiter

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

# Broker statements are small; guard against oversized uploads (5 MB).
_MAX_IMPORT_BYTES = 5 * 1024 * 1024

@router.get("", response_model=list[HoldingResponse])
def handle_get_portfolio(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    return PortfolioService.get_portfolio(user_id)

@router.get("/analytics")
def handle_get_portfolio_analytics(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    return PortfolioService.get_portfolio_analytics(user_id)

@router.post("/add", response_model=dict)
@limiter.limit("15/minute")
def handle_add_holding(
    payload: HoldingCreate, 
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    user_id = str(current_user["id"])
    holding_id = PortfolioService.add_holding(
        user_id=user_id,
        symbol=payload.symbol,
        company_name=payload.company_name or "",
        quantity=payload.quantity,
        buy_price=payload.buy_price
    )
    if holding_id is None:
        raise HTTPException(status_code=500, detail="Failed to add stock holding")
    return {"id": holding_id, "success": True, "message": "Holding added successfully."}

@router.post("/import/preview")
@limiter.limit("10/minute")
async def handle_import_preview(
    request: Request,
    file: UploadFile = File(...),
    broker: str = Form("auto"),
    current_user: dict = Depends(get_current_user),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > _MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Max 5 MB.")
    try:
        return PortfolioService.preview_import(content, file.filename or "", broker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this file. Please upload a valid broker holdings export (CSV or XLSX).")

@router.post("/import/commit", response_model=dict)
@limiter.limit("10/minute")
def handle_import_commit(
    payload: ImportCommit,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])
    holdings = [h.model_dump() for h in payload.holdings]
    inserted = PortfolioService.commit_import(user_id, holdings)
    if inserted == 0:
        raise HTTPException(status_code=500, detail="Failed to import holdings.")
    return {"success": True, "imported": inserted, "message": f"Imported {inserted} holding(s)."}

@router.delete("/remove/{holding_id}", response_model=dict)
def handle_remove_holding(holding_id: int, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["id"])
    success = PortfolioService.remove_holding(holding_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Holding not found or unauthorized to delete")
    return {"success": True, "message": "Holding removed successfully."}
