from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Security, Request
from fastapi.security import APIKeyHeader
import os
from app.core.limiter import limiter

router = APIRouter(prefix="/admin", tags=["Admin Tools"])

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
if not ADMIN_TOKEN:
    raise ValueError("ADMIN_TOKEN is not set in environment variables")
api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=True)

async def verify_admin_token(api_key: str = Security(api_key_header)):
    if api_key != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return api_key

@router.post("/trigger-training")
@limiter.limit("2/hour")
def trigger_training(
    request: Request,
    background_tasks: BackgroundTasks, 
    token: str = Depends(verify_admin_token)
):
    """
    Triggers the XGBoost ML training script in the background.
    Protected by X-Admin-Token header.
    """
    from scripts.train_xgboost import run_training_job
    background_tasks.add_task(run_training_job, all_symbols=True, force=True)
    return {"status": "success", "message": "Background ML training job started"}
