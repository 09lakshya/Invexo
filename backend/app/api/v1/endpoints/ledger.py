"""
Signal Ledger API (Phase 1).

Read-only over the append-only ledger — there is deliberately NO POST/PUT/
DELETE that mutates signals. The only write route triggers a scan (admin,
for verification); the ledger itself remains append-only.
"""

import csv
import io
import threading

from fastapi import APIRouter, Depends, Query, Security
from fastapi.responses import StreamingResponse

from app.api.v1.dependencies import require_role
from app.api.v1.endpoints.admin import verify_admin_token
from app.repositories.signal_repository import SignalRepository, CONFIDENCE_BUCKETS
from app.services.ai.signal_ledger_service import (
    SignalLedgerService, build_stats, build_signal_list, flatten_for_csv,
    SIGNAL_UNIVERSE,
)
from app.utils.logger import get_logger

logger = get_logger("ledger")

router = APIRouter(prefix="/ledger", tags=["Signal Ledger"])

_ANY_USER = require_role(["user", "premium", "admin"])
_BUCKET_LABELS = [b[0] for b in CONFIDENCE_BUCKETS]


@router.get("/signals")
def list_signals(
    ticker: str | None = None,
    start: str | None = Query(None, description="Inclusive start date YYYY-MM-DD (UTC)"),
    end: str | None = Query(None, description="Inclusive end date YYYY-MM-DD (UTC)"),
    regime: str | None = Query(None, description="trending | range_bound"),
    bucket: str | None = Query(None, description="Confidence bucket, e.g. 65-80"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(_ANY_USER),
):
    """Filterable, paginated signal table with nested per-horizon outcomes."""
    if bucket and bucket not in _BUCKET_LABELS:
        bucket = None
    rows = SignalRepository._fetch_joined(ticker=ticker, start=start, end=end,
                                          regime=regime, bucket=bucket)
    return build_signal_list(rows, limit=limit, offset=offset)


@router.get("/stats")
def ledger_stats(
    start: str | None = None,
    end: str | None = None,
    regime: str | None = None,
    bucket: str | None = None,
    current_user: dict = Depends(_ANY_USER),
):
    """Realized hit rate + average return, overall and broken down per regime,
    per confidence bucket and per horizon. Accuracy is always paired with the
    return it produced."""
    if bucket and bucket not in _BUCKET_LABELS:
        bucket = None
    rows = SignalRepository._fetch_joined(start=start, end=end, regime=regime, bucket=bucket)
    stats = build_stats(rows)
    stats["buckets"] = _BUCKET_LABELS
    stats["universe_size"] = len(SIGNAL_UNIVERSE)
    return stats


@router.get("/coverage")
def scan_coverage(day: str, current_user: dict = Depends(_ANY_USER)):
    """Per-scan symbol counts for a day — evidence of gap-free session
    coverage (the Phase 1 gate)."""
    return {"day": day, "scans": SignalRepository.get_scan_coverage(day)}


@router.get("/export.csv")
def export_csv(
    ticker: str | None = None,
    start: str | None = None,
    end: str | None = None,
    regime: str | None = None,
    bucket: str | None = None,
    current_user: dict = Depends(_ANY_USER),
):
    """Flattened one-row-per-(signal,horizon) CSV for offline analysis."""
    if bucket and bucket not in _BUCKET_LABELS:
        bucket = None
    rows = SignalRepository._fetch_joined(ticker=ticker, start=start, end=end,
                                          regime=regime, bucket=bucket)
    records = flatten_for_csv(rows)
    fields = [
        "signal_id", "signal_ts", "symbol", "direction", "confidence",
        "confidence_bucket", "regime", "sentiment_score", "entry_price",
        "rsi", "adx", "volatility", "model_version", "horizon", "exit_price",
        "return_pct", "hit", "mae_pct", "scored_ts",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for rec in records:
        writer.writerow(rec)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=signal_ledger.csv"},
    )


@router.post("/scan")
def trigger_scan(_: str = Security(verify_admin_token)):
    """Admin-only: run a signal scan now (for local verification). The ledger
    stays append-only — this just generates new rows."""
    thread = threading.Thread(target=SignalLedgerService.generate_signals, kwargs={"force": True})
    thread.daemon = True
    thread.start()
    return {"status": "accepted", "message": "Signal scan started in background."}
