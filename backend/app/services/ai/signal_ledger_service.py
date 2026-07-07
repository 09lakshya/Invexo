"""
Signal Ledger service (Phase 1).

Two scheduled responsibilities:

  1. generate_signals()       — during the trading session, run the consensus
                                predictor over a fixed watchlist and APPEND one
                                immutable ledger row per symbol.
  2. score_pending_outcomes() — fill realized outcomes (return %, hit, max
                                adverse excursion) at the 1h / 1d / 3d horizons
                                once each horizon has elapsed and price data is
                                available. Written exactly once per horizon.

Plus the pure functions the scoring/scan math depends on (return, hit, MAE,
direction and regime mapping). These decide realized P&L, so they live here as
small, side-effect-free helpers and are covered by tests/test_signal_ledger.py.

Data source: yfinance (the same vendor used everywhere else in the repo) via
the shared browser-impersonation session. 1d/3d are scored from daily bars;
1h from 60-minute intraday bars. If data is missing for a signal, its outcome
is left UNSCORED rather than fabricated.
"""

import uuid
import json
from datetime import datetime, timezone, timedelta

from app.repositories.signal_repository import SignalRepository, HORIZONS, confidence_bucket
from app.services.ai.prediction_service import PredictionService, MODEL_VERSION
from app.utils.logger import get_logger

logger = get_logger("signal_ledger_service")

# Focused, liquid NSE watchlist scanned each session. Editable — kept small
# because predict_stock is heavy and the shared yfinance session is not
# thread-safe, so symbols are scored roughly sequentially.
SIGNAL_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "HINDUNILVR.NS", "BAJFINANCE.NS",
    "LT.NS", "KOTAKBANK.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "NTPC.NS",
    "POWERGRID.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "ADANIENT.NS", "COALINDIA.NS",
    "ONGC.NS", "HCLTECH.NS", "TECHM.NS", "M&M.NS", "TATAMOTORS.NS",
]

# Horizon lengths. 1h is wall-clock; 1d/3d are measured in *trading* days at
# scoring time (the Nth daily close strictly after the signal date).
HORIZON_DELTA = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
}
# Trading-day offset used when scoring against daily bars (1-indexed position
# among trading days strictly after the signal date).
TRADING_DAY_OFFSET = {"1d": 1, "3d": 3}


# ── Pure helpers (unit-tested — these decide realized P&L) ────────────────

def direction_from_trend(trend: str) -> str:
    """Consensus trend label → position direction."""
    t = (trend or "").upper()
    if t == "BULLISH":
        return "long"
    if t == "BEARISH":
        return "short"
    return "neutral"


def regime_from_adx(adx) -> str:
    """ADX > 25 ⇒ trending tape, else range-bound. Mirrors the threshold the
    consensus weighting already uses."""
    try:
        return "trending" if float(adx) > 25 else "range_bound"
    except (TypeError, ValueError):
        return "range_bound"


def compute_return(entry: float, exit_price: float, direction: str) -> float:
    """Signed return of the *position* (not the underlying). A short profits
    when price falls, so its return is inverted. Neutral is reported as the
    raw underlying move (informational only)."""
    if entry is None or exit_price is None or entry == 0:
        raise ValueError("entry and exit must be non-zero numbers")
    raw = (exit_price - entry) / entry
    if direction == "short":
        return -raw
    return raw  # long and neutral use the raw move


def is_hit(return_pct: float, direction: str) -> int | None:
    """1 if the position made money, 0 if it lost. Neutral signals have no
    directional bet, so their hit is undefined (None) and they are excluded
    from hit-rate stats."""
    if direction == "neutral":
        return None
    return 1 if return_pct > 0 else 0


def max_adverse_excursion(entry: float, lows: list[float], highs: list[float],
                          direction: str) -> float | None:
    """Worst *unrealized* move against the position over the horizon window,
    as a signed fraction (≤ 0; more negative = deeper adverse move).

    - long:  hurt by the lowest low  → min((low - entry) / entry)
    - short: hurt by the highest high → -max((high - entry) / entry)
    - neutral: the larger absolute excursion in either direction (worst case)
    """
    if entry in (None, 0) or not lows or not highs:
        return None
    down = min((lo - entry) / entry for lo in lows)          # ≤ 0
    up = max((hi - entry) / entry for hi in highs)           # ≥ 0
    if direction == "long":
        return down
    if direction == "short":
        return -up
    # neutral: whichever side moved further from entry
    return -max(abs(down), abs(up))


def map_prediction_to_signal(symbol: str, pred: dict, scan_id: str,
                             signal_ts: str) -> dict | None:
    """Convert a predict_stock payload into a ledger row. Returns None if the
    prediction errored or lacks the fields needed to score it later."""
    if not pred or "error" in pred:
        return None
    entry = pred.get("current_price")
    if entry is None:
        return None
    return {
        "signal_ts": signal_ts,
        "scan_id": scan_id,
        "symbol": symbol,
        "direction": direction_from_trend(pred.get("trend")),
        "confidence": pred.get("confidence"),
        "regime": pred.get("regime") or regime_from_adx(pred.get("adx")),
        "indicator_states": pred.get("indicator_states"),
        "sentiment_score": pred.get("news_sentiment"),
        "entry_price": entry,
        "adx": pred.get("adx"),
        "rsi": pred.get("rsi"),
        "volatility": pred.get("volatility"),
        "model_version": pred.get("model_version") or MODEL_VERSION,
        "corrects_signal_id": None,
        "raw_prediction": pred,
    }


# ── Aggregation for the API (pure over rows returned by the repo) ─────────

def _empty_horizon_stat():
    return {"n": 0, "hits": 0, "ret_sum": 0.0}


def build_stats(rows: list[dict]) -> dict:
    """Aggregate joined signal/outcome rows into overall + per-regime +
    per-bucket + per-horizon hit rates and average returns. Accuracy is never
    reported without its return alongside."""
    overall = {h: _empty_horizon_stat() for h in HORIZONS}
    by_regime: dict[str, dict] = {}
    by_bucket: dict[str, dict] = {}
    signals_seen = set()

    for r in rows:
        signals_seen.add(r["signal_id"])
        h = r.get("horizon")
        if not h or r.get("return_pct") is None:
            continue
        ret = float(r["return_pct"])
        hit = r.get("hit")
        regime = r.get("regime") or "unknown"
        bucket = confidence_bucket(r.get("confidence")) or "unknown"

        for scope, key in ((overall, None), (by_regime, regime), (by_bucket, bucket)):
            if key is None:
                bucketed = overall
            else:
                bucketed = scope.setdefault(key, {hh: _empty_horizon_stat() for hh in HORIZONS})
            st = bucketed[h]
            st["n"] += 1
            st["ret_sum"] += ret
            if hit is not None:
                st["hits"] += int(hit)

    def finalize(group):
        out = {}
        for h in HORIZONS:
            st = group[h]
            n = st["n"]
            out[h] = {
                "evaluated": n,
                "hit_rate": round(st["hits"] / n * 100, 1) if n else None,
                "avg_return_pct": round(st["ret_sum"] / n * 100, 2) if n else None,
            }
        return out

    return {
        "total_signals": len(signals_seen),
        "overall": finalize(overall),
        "by_regime": {k: finalize(v) for k, v in sorted(by_regime.items())},
        "by_confidence_bucket": {k: finalize(v) for k, v in sorted(by_bucket.items())},
    }


def build_signal_list(rows: list[dict], limit: int, offset: int) -> dict:
    """Group joined rows into one entry per signal (outcomes nested), sorted
    newest-first, then paginate over signals."""
    order: list[int] = []
    by_id: dict[int, dict] = {}
    for r in rows:
        sid = r["signal_id"]
        if sid not in by_id:
            order.append(sid)
            states = r.get("indicator_states")
            if isinstance(states, str):
                try:
                    states = json.loads(states)
                except Exception:
                    states = None
            by_id[sid] = {
                "signal_id": sid,
                "signal_ts": r["signal_ts"],
                "symbol": r["symbol"],
                "direction": r["direction"],
                "confidence": r.get("confidence"),
                "confidence_bucket": confidence_bucket(r.get("confidence")),
                "regime": r.get("regime"),
                "sentiment_score": r.get("sentiment_score"),
                "entry_price": r.get("entry_price"),
                "rsi": r.get("rsi"),
                "adx": r.get("adx"),
                "model_version": r.get("model_version"),
                "indicator_states": states,
                "outcomes": {},
            }
        if r.get("horizon"):
            by_id[sid]["outcomes"][r["horizon"]] = {
                "return_pct": round(float(r["return_pct"]) * 100, 2) if r.get("return_pct") is not None else None,
                "hit": r.get("hit"),
                "mae_pct": round(float(r["mae_pct"]) * 100, 2) if r.get("mae_pct") is not None else None,
                "exit_price": r.get("exit_price"),
            }
    total = len(order)
    page = [by_id[sid] for sid in order[offset:offset + limit]]
    return {"total": total, "count": len(page), "offset": offset, "limit": limit, "signals": page}


def flatten_for_csv(rows: list[dict]) -> list[dict]:
    """One flat record per (signal, horizon) — signals with no outcome yet get
    a single record with empty outcome columns. Suitable for offline analysis."""
    out = []
    seen_unscored = set()
    for r in rows:
        base = {
            "signal_id": r["signal_id"],
            "signal_ts": r["signal_ts"],
            "symbol": r["symbol"],
            "direction": r["direction"],
            "confidence": r.get("confidence"),
            "confidence_bucket": confidence_bucket(r.get("confidence")),
            "regime": r.get("regime"),
            "sentiment_score": r.get("sentiment_score"),
            "entry_price": r.get("entry_price"),
            "rsi": r.get("rsi"),
            "adx": r.get("adx"),
            "volatility": r.get("volatility"),
            "model_version": r.get("model_version"),
        }
        if r.get("horizon"):
            base.update({
                "horizon": r["horizon"],
                "exit_price": r.get("exit_price"),
                "return_pct": round(float(r["return_pct"]) * 100, 4) if r.get("return_pct") is not None else None,
                "hit": r.get("hit"),
                "mae_pct": round(float(r["mae_pct"]) * 100, 4) if r.get("mae_pct") is not None else None,
                "scored_ts": r.get("scored_ts"),
            })
            out.append(base)
        else:
            if r["signal_id"] in seen_unscored:
                continue
            seen_unscored.add(r["signal_id"])
            base.update({"horizon": None, "exit_price": None, "return_pct": None,
                         "hit": None, "mae_pct": None, "scored_ts": None})
            out.append(base)
    return out


# ── Scheduled jobs ────────────────────────────────────────────────────────

class SignalLedgerService:
    @staticmethod
    def generate_signals(force: bool = False) -> dict:
        """Scan the watchlist and append a signal row per symbol. Skips
        weekends unless forced (NSE holidays are a known gap — see
        implementation-notes.md)."""
        now = datetime.now(timezone.utc)
        # IST weekday check: NSE trades Mon–Fri. now is UTC; IST = UTC+5:30,
        # which never crosses a weekday boundary for session hours, so the
        # UTC weekday is a safe proxy here.
        if not force and now.weekday() >= 5:
            logger.info("Signal scan skipped (weekend).")
            return {"scanned": 0, "logged": 0, "skipped": "weekend"}

        scan_id = f"scan_{now.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
        signal_ts = now.isoformat()
        logged = 0
        for symbol in SIGNAL_UNIVERSE:
            try:
                pred = PredictionService.predict_stock(symbol)
                sig = map_prediction_to_signal(symbol, pred, scan_id, signal_ts)
                if sig is None:
                    logger.warning(f"Signal scan: no usable prediction for {symbol}")
                    continue
                if SignalRepository.insert_signal(sig) is not None:
                    logged += 1
            except Exception as e:
                logger.error(f"Signal scan error for {symbol}: {e}")

        logger.info(f"Signal scan {scan_id}: logged {logged}/{len(SIGNAL_UNIVERSE)} signals.")
        return {"scan_id": scan_id, "scanned": len(SIGNAL_UNIVERSE), "logged": logged}

    @staticmethod
    def _parse_ts(ts: str) -> datetime:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def score_pending_outcomes() -> dict:
        """Fill 1h/1d/3d outcomes for signals whose horizon has elapsed and
        whose price data is available. Idempotent; never fabricates."""
        import pandas as pd
        import yfinance as yf
        from app.services.market.ticker_utils import _yf_session

        pending = SignalRepository.get_signals_pending_scoring(within_days=10)
        if not pending:
            return {"filled": 0}

        now = datetime.now(timezone.utc)

        # Work out what's actually due (elapsed) per signal.
        due_daily = {}   # symbol -> True if any 1d/3d due
        due_intra = {}   # symbol -> True if any 1h due
        for s in pending:
            sig_ts = SignalLedgerService._parse_ts(s["signal_ts"])
            s["_sig_ts"] = sig_ts
            for h in HORIZONS:
                if h in s["scored_horizons"]:
                    continue
                if now < sig_ts + HORIZON_DELTA[h]:
                    continue
                if h == "1h":
                    due_intra[s["symbol"]] = True
                else:
                    due_daily[s["symbol"]] = True

        if not due_daily and not due_intra:
            return {"filled": 0}

        # Batch daily download for 1d/3d.
        daily = {}
        if due_daily:
            syms = sorted(due_daily)
            try:
                raw = yf.download(tickers=" ".join(syms), period="1mo", interval="1d",
                                  group_by="ticker", auto_adjust=True, threads=False,
                                  progress=False, session=_yf_session)
                for sym in syms:
                    try:
                        df = raw[sym] if isinstance(raw.columns, pd.MultiIndex) else raw
                        daily[sym] = df.dropna(subset=["Close"])
                    except Exception:
                        continue
            except Exception as e:
                logger.error(f"Daily outcome download failed: {e}")

        # Per-symbol intraday (60m) download for 1h.
        intraday = {}
        for sym in sorted(due_intra):
            try:
                df = yf.download(tickers=sym, period="1mo", interval="60m",
                                 auto_adjust=True, threads=False, progress=False,
                                 session=_yf_session)
                if isinstance(df.columns, pd.MultiIndex):
                    df = df[sym]
                intraday[sym] = df.dropna(subset=["Close"])
            except Exception as e:
                logger.error(f"Intraday outcome download failed for {sym}: {e}")

        filled = 0
        scored_ts = now.isoformat()
        for s in pending:
            sig_ts = s["_sig_ts"]
            entry = float(s["entry_price"])
            direction = s["direction"]
            for h in HORIZONS:
                if h in s["scored_horizons"] or now < sig_ts + HORIZON_DELTA[h]:
                    continue
                try:
                    if h == "1h":
                        res = SignalLedgerService._score_intraday(intraday.get(s["symbol"]), sig_ts, entry, direction)
                    else:
                        res = SignalLedgerService._score_daily(daily.get(s["symbol"]), sig_ts, entry, direction, TRADING_DAY_OFFSET[h])
                    if res is None:
                        continue  # data not available yet — retry next run
                    exit_price, ret, mae = res
                    if SignalRepository.record_outcome(
                        s["signal_id"], h, scored_ts, round(exit_price, 4),
                        round(ret, 6), is_hit(ret, direction),
                        round(mae, 6) if mae is not None else None,
                    ):
                        filled += 1
                except Exception as e:
                    logger.error(f"Scoring error signal {s['signal_id']}/{h}: {e}")

        logger.info(f"Signal scoring: filled {filled} outcomes across {len(pending)} pending signals.")
        return {"filled": filled}

    @staticmethod
    def _score_daily(df, sig_ts: datetime, entry: float, direction: str, offset: int):
        """Score against the `offset`-th daily close strictly after the signal
        date. Returns (exit_price, return, mae) or None if not enough data."""
        import pandas as pd
        if df is None or df.empty:
            return None
        closes = df["Close"].dropna()
        if closes.empty:
            return None
        idx = pd.to_datetime(closes.index)
        idx_dates = [d.date() for d in idx]
        sig_date = sig_ts.date()
        after = [i for i, d in enumerate(idx_dates) if d > sig_date]
        if len(after) < offset:
            return None
        window = after[:offset]  # trading days 1..offset after the signal
        exit_price = float(closes.iloc[after[offset - 1]])
        ret = compute_return(entry, exit_price, direction)
        lows = [float(df["Low"].iloc[i]) for i in window]
        highs = [float(df["High"].iloc[i]) for i in window]
        mae = max_adverse_excursion(entry, lows, highs, direction)
        return exit_price, ret, mae

    @staticmethod
    def _score_intraday(df, sig_ts: datetime, entry: float, direction: str):
        """Score against the first 60m bar at/after signal time + 1h. Returns
        (exit_price, return, mae) or None if intraday data isn't there yet."""
        import pandas as pd
        if df is None or df.empty:
            return None
        idx = pd.to_datetime(df.index, utc=True)
        target = sig_ts + HORIZON_DELTA["1h"]
        positions = [i for i, t in enumerate(idx) if t >= target]
        if not positions:
            return None
        end = positions[0]
        start_positions = [i for i, t in enumerate(idx) if t >= sig_ts]
        start = start_positions[0] if start_positions else end
        exit_price = float(df["Close"].iloc[end])
        ret = compute_return(entry, exit_price, direction)
        window = range(start, end + 1)
        lows = [float(df["Low"].iloc[i]) for i in window]
        highs = [float(df["High"].iloc[i]) for i in window]
        mae = max_adverse_excursion(entry, lows, highs, direction)
        return exit_price, ret, mae
