"""
Walk-forward backtest API (Phase 2).

POST /backtest/run    — run a walk-forward backtest with honest costs.
GET  /backtest/config — defaults: cost model, suggested universe, param ranges.
"""

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
    symbols = [s.strip().upper() for s in body.symbols if s.strip()]
    symbols = [s if (s.endswith(".NS") or s.endswith(".BO")) else f"{s}.NS" for s in symbols]
    if not symbols:
        raise HTTPException(status_code=400, detail="At least one symbol is required.")

    cfg = BacktestConfig(
        symbols=symbols, start=body.start, end=body.end,
        holding_days=body.holding_days, initial_capital=body.initial_capital,
        trade_fraction=body.trade_fraction, n_folds=body.n_folds,
        cost_overrides=body.cost_overrides,
    )
    try:
        result = WalkForwardBacktest().run(cfg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest run failed: {e}")
        raise HTTPException(status_code=500, detail="Backtest failed. Please try again.")
    return result
