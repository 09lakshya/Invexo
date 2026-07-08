"""
Walk-forward backtest API (Phase 2).

POST /backtest/run    — run a walk-forward backtest with honest costs.
GET  /backtest/config — defaults: cost model, suggested universe, param ranges.
"""

import threading
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.v1.dependencies import require_role
from app.core.limiter import limiter
from app.services.ai.backtest.cost_model import CostModel
from app.services.ai.backtest.walkforward_backtest import (
    WalkForwardBacktest, BacktestConfig, CONFIDENCE_GRID,
)
from app.services.ai.signal_ledger_service import SIGNAL_UNIVERSE
from app.utils.logger import get_logger

logger = get_logger("backtest")

router = APIRouter(prefix="/backtest", tags=["Backtest"])
_ANY_USER = require_role(["user", "premium", "admin"])

# ── Async job registry ──────────────────────────────────────────────────────
# A walk-forward run can take longer than the ~100s proxy (Cloudflare) timeout,
# which drops the connection and surfaces in the browser as a misleading CORS
# error. We run it in a background thread and let the client poll for the
# result instead. The API is a single uvicorn worker, so an in-process dict is
# sufficient (no cross-worker coordination needed); results are pruned on a TTL.
_JOBS: dict = {}
_JOBS_LOCK = threading.Lock()
_JOB_TTL_SECS = 600      # keep a finished result available for 10 minutes
_JOB_MAX = 100           # hard cap on retained jobs


def _prune_jobs() -> None:
    now = time.time()
    with _JOBS_LOCK:
        stale = [jid for jid, j in _JOBS.items() if now - j["updated"] > _JOB_TTL_SECS]
        for jid in stale:
            _JOBS.pop(jid, None)
        if len(_JOBS) > _JOB_MAX:
            for jid in sorted(_JOBS, key=lambda k: _JOBS[k]["updated"])[: len(_JOBS) - _JOB_MAX]:
                _JOBS.pop(jid, None)


def _set_job(job_id: str, **fields) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is not None:
            job.update(updated=time.time(), **fields)


def _run_job(job_id: str, cfg: "BacktestConfig") -> None:
    try:
        result = WalkForwardBacktest().run(cfg)
        _set_job(job_id, status="done", result=result)
    except ValueError as e:
        _set_job(job_id, status="error", error=str(e), code=400)
    except Exception as e:
        logger.error(f"Async backtest job {job_id} failed: {e}")
        _set_job(job_id, status="error", error="Backtest failed. Please try again.", code=500)


def _prepare_config(body: "BacktestRequest") -> "BacktestConfig":
    symbols = [s.strip().upper() for s in body.symbols if s.strip()]
    symbols = [s if (s.endswith(".NS") or s.endswith(".BO")) else f"{s}.NS" for s in symbols]
    if not symbols:
        raise HTTPException(status_code=400, detail="At least one symbol is required.")
    return BacktestConfig(
        symbols=symbols, start=body.start, end=body.end,
        holding_days=body.holding_days, initial_capital=body.initial_capital,
        trade_fraction=body.trade_fraction, n_folds=body.n_folds,
        cost_overrides=body.cost_overrides,
    )


class BacktestRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=40)
    start: Optional[str] = None
    end: Optional[str] = None
    holding_days: int = Field(3, ge=1, le=20)
    initial_capital: float = Field(100000.0, gt=0)
    trade_fraction: float = Field(0.1, gt=0, le=1.0)
    n_folds: int = Field(4, ge=2, le=8)
    cost_overrides: dict = Field(default_factory=dict)


@router.get("/config")
def backtest_config(current_user: dict = Depends(_ANY_USER)):
    """Defaults for the config panel: cost model, universe, and param ranges."""
    return {
        "cost_model_defaults": CostModel().to_dict(),
        "cost_model_docs": {
            "brokerage_rate": "Per-order brokerage as a fraction of turnover (capped).",
            "brokerage_cap": "Max brokerage per order (₹).",
            "stt_rate": "Securities Transaction Tax, both sides (delivery).",
            "exchange_txn_rate": "NSE exchange transaction charge, both sides.",
            "sebi_rate": "SEBI turnover fee (₹10/crore), both sides.",
            "gst_rate": "GST on brokerage + exchange + SEBI.",
            "stamp_rate": "Stamp duty, buy side only.",
            "slippage_bps": "Adverse fill per side, basis points.",
        },
        "suggested_universe": SIGNAL_UNIVERSE,
        "confidence_grid": CONFIDENCE_GRID,
        "param_ranges": {"holding_days": [1, 20], "n_folds": [2, 8],
                         "trade_fraction": [0.01, 1.0], "max_symbols": 40},
        "notes": [
            "Walk-forward only: confidence threshold calibrated on past, tested on next.",
            "NLP sentiment and fundamentals are held neutral (no point-in-time archive).",
            "Daily bars; entries at next-day open, exit at close after holding_days.",
        ],
    }


@router.post("/run")
@limiter.limit("6/minute")
def run_backtest(request: Request, body: BacktestRequest, current_user: dict = Depends(_ANY_USER)):
    """Synchronous run. Kept for small jobs and as a fallback; heavy runs should
    use /run-async to avoid the proxy request timeout."""
    cfg = _prepare_config(body)
    try:
        result = WalkForwardBacktest().run(cfg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest run failed: {e}")
        raise HTTPException(status_code=500, detail="Backtest failed. Please try again.")
    return result


@router.post("/run-async")
@limiter.limit("6/minute")
def run_backtest_async(request: Request, body: BacktestRequest, current_user: dict = Depends(_ANY_USER)):
    """Kick off a walk-forward run in the background and return a job id. The
    client polls GET /backtest/jobs/{job_id} for the result. This keeps every
    HTTP call well under the proxy timeout no matter how long the run takes."""
    cfg = _prepare_config(body)
    _prune_jobs()
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "status": "running", "result": None, "error": None, "code": None,
            "user_id": current_user["id"], "updated": time.time(),
        }
    threading.Thread(target=_run_job, args=(job_id, cfg), daemon=True).start()
    return {"job_id": job_id, "status": "running"}


@router.get("/jobs/{job_id}")
def backtest_job_status(job_id: str, current_user: dict = Depends(_ANY_USER)):
    """Poll a background backtest. Returns {status: running|done|error}, with
    the result on completion or a detail message on failure."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        # Scope jobs to their owner; don't leak existence of others' jobs.
        if job is None or job["user_id"] != current_user["id"]:
            raise HTTPException(status_code=404, detail="Job not found or expired.")
        status, result, error, code = job["status"], job["result"], job["error"], job["code"]

    if status == "done":
        return {"status": "done", "result": result}
    if status == "error":
        return {"status": "error", "detail": error, "code": code}
    return {"status": "running"}
