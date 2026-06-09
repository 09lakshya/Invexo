from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Security
from fastapi.security import APIKeyHeader
import os

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Very simple security for the cron job ping
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "invexo-nightly-ml")
api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=True)

async def verify_admin_token(api_key: str = Security(api_key_header)):
    if api_key != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return api_key

@router.post("/trigger-training")
async def trigger_training(background_tasks: BackgroundTasks, token: str = Depends(verify_admin_token)):
    """
    Triggers the XGBoost ML training script in the background.
    Protected by X-Admin-Token header.
    """
    from scripts.train_xgboost import run_training_job
    # Run in background so the caller doesn't timeout waiting for 2000+ models to train
    background_tasks.add_task(run_training_job, all_symbols=True, force=True)
    return {"status": "success", "message": "Background ML training job started"}
