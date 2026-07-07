"""
Tests for Signal Ledger P&L / scoring math and the append-only ledger.

These functions decide realized returns, so they are covered directly:
direction-aware return, hit, max adverse excursion, regime mapping, the
daily/intraday scorers (against synthetic price frames — no network), stats
aggregation, and the structural guarantee that the ledger has no mutation path.
"""

import math
from datetime import datetime, timezone

import pandas as pd
import pytest

from app.services.ai.signal_ledger_service import (
    direction_from_trend, regime_from_adx, compute_return, is_hit,
    max_adverse_excursion, map_prediction_to_signal, build_stats,
    SignalLedgerService,
)
from app.repositories.signal_repository import (
    SignalRepository, confidence_bucket, HORIZONS,
)

UTC = timezone.utc


# ── Direction & regime mapping ────────────────────────────────────────────
def test_direction_from_trend():
    assert direction_from_trend("BULLISH") == "long"
    assert direction_from_trend("BEARISH") == "short"
    assert direction_from_trend("NEUTRAL") == "neutral"
    assert direction_from_trend(None) == "neutral"


def test_regime_from_adx():
    assert regime_from_adx(30) == "trending"
    assert regime_from_adx(25) == "range_bound"   # threshold is strict >
    assert regime_from_adx(10) == "range_bound"
    assert regime_from_adx(None) == "range_bound"


# ── Direction-aware return (the core money math) ──────────────────────────
def test_return_long():
    assert compute_return(100, 110, "long") == pytest.approx(0.10)
    assert compute_return(100, 90, "long") == pytest.approx(-0.10)


def test_return_short_inverts():
    # A short makes money when price falls.
    assert compute_return(100, 90, "short") == pytest.approx(0.10)
    assert compute_return(100, 110, "short") == pytest.approx(-0.10)


def test_return_neutral_is_raw_move():
    assert compute_return(100, 105, "neutral") == pytest.approx(0.05)


def test_return_rejects_zero_entry():
    with pytest.raises(ValueError):
        compute_return(0, 10, "long")


# ── Hit ───────────────────────────────────────────────────────────────────
def test_is_hit_directional():
    assert is_hit(0.05, "long") == 1
    assert is_hit(-0.01, "long") == 0
    # return is already position-signed, so short uses the same rule
    assert is_hit(0.05, "short") == 1
    assert is_hit(-0.05, "short") == 0
    assert is_hit(0.05, "neutral") is None


# ── Max adverse excursion ─────────────────────────────────────────────────
def test_mae_long_uses_lowest_low():
    # entry 100, lowest low 92 → worst unrealized -8%
    mae = max_adverse_excursion(100, lows=[98, 92, 95], highs=[105, 103, 108], direction="long")
    assert mae == pytest.approx(-0.08)


def test_mae_short_uses_highest_high():
    # entry 100, highest high 112 → short is hurt by upside → -12%
    mae = max_adverse_excursion(100, lows=[95, 97], highs=[104, 112], direction="short")
    assert mae == pytest.approx(-0.12)


def test_mae_neutral_worst_of_both_sides():
    mae = max_adverse_excursion(100, lows=[97], highs=[115], direction="neutral")
    assert mae == pytest.approx(-0.15)


# ── Confidence buckets ────────────────────────────────────────────────────
def test_confidence_bucket_boundaries():
    assert confidence_bucket(35) == "35-50"
    assert confidence_bucket(49.9) == "35-50"
    assert confidence_bucket(50) == "50-65"
    assert confidence_bucket(80) == "80-95"
    assert confidence_bucket(95) == "80-95"
    assert confidence_bucket(None) is None


# ── Prediction → signal mapping ───────────────────────────────────────────
def test_map_prediction_to_signal():
    pred = {
        "current_price": 250.5, "trend": "BEARISH", "confidence": 72,
        "regime": "trending", "adx": 31.2, "rsi": 44.0, "volatility": 1.8,
        "news_sentiment": 41.0, "model_version": "consensus_v1.0",
        "indicator_states": {"macd": "BEARISH"},
    }
    sig = map_prediction_to_signal("RELIANCE.NS", pred, "scan_x", "2026-07-06T09:20:00+00:00")
    assert sig["direction"] == "short"
    assert sig["entry_price"] == 250.5
    assert sig["regime"] == "trending"
    assert sig["sentiment_score"] == 41.0
    assert sig["model_version"] == "consensus_v1.0"


def test_map_prediction_skips_errors():
    assert map_prediction_to_signal("X.NS", {"error": "no data"}, "s", "t") is None
    assert map_prediction_to_signal("X.NS", {}, "s", "t") is None


# ── Daily scorer (synthetic frame, no network) ────────────────────────────
def _daily_frame():
    idx = pd.date_range("2026-07-06", periods=6, freq="D", tz="UTC")
    return pd.DataFrame({
        "Open":  [100, 101, 103, 104, 106, 108],
        "High":  [101, 106, 105, 112, 109, 111],
        "Low":   [ 99,  97, 101,  98, 104, 107],
        "Close": [100, 105, 104, 110, 107, 109],
    }, index=idx)


def test_score_daily_1d_long():
    df = _daily_frame()
    sig_ts = datetime(2026, 7, 6, tzinfo=UTC)
    exit_price, ret, mae = SignalLedgerService._score_daily(df, sig_ts, entry=100, direction="long", offset=1)
    assert exit_price == 105                      # next trading day's close
    assert ret == pytest.approx(0.05)
    assert mae == pytest.approx((97 - 100) / 100) # that day's low = 97


def test_score_daily_3d_long_window_mae():
    df = _daily_frame()
    sig_ts = datetime(2026, 7, 6, tzinfo=UTC)
    exit_price, ret, mae = SignalLedgerService._score_daily(df, sig_ts, entry=100, direction="long", offset=3)
    assert exit_price == 110                       # 3rd trading day close
    assert ret == pytest.approx(0.10)
    # lowest low across days 1..3 (97, 101, 98) = 97
    assert mae == pytest.approx((97 - 100) / 100)


def test_score_daily_short_direction():
    df = _daily_frame()
    sig_ts = datetime(2026, 7, 6, tzinfo=UTC)
    _, ret, mae = SignalLedgerService._score_daily(df, sig_ts, entry=100, direction="short", offset=1)
    assert ret == pytest.approx(-0.05)             # price rose → short loses
    assert mae == pytest.approx((100 - 106) / 100) # hurt by day-1 high 106


def test_score_daily_insufficient_data_returns_none():
    df = _daily_frame()
    sig_ts = datetime(2026, 7, 20, tzinfo=UTC)     # after all bars
    assert SignalLedgerService._score_daily(df, sig_ts, 100, "long", 1) is None


# ── Intraday (1h) scorer ──────────────────────────────────────────────────
def test_score_intraday_1h():
    idx = pd.date_range("2026-07-06 09:15", periods=6, freq="60min", tz="UTC")
    df = pd.DataFrame({
        "Open":  [100, 101, 102, 103, 104, 105],
        "High":  [101, 103, 104, 105, 106, 107],
        "Low":   [ 99,  98, 101, 102, 103, 104],
        "Close": [100, 102, 103, 104, 105, 106],
    }, index=idx)
    sig_ts = datetime(2026, 7, 6, 9, 15, tzinfo=UTC)
    exit_price, ret, mae = SignalLedgerService._score_intraday(df, sig_ts, entry=100, direction="long")
    # target = 10:15 → first bar at/after is index 1 (10:15), Close 102
    assert exit_price == 102
    assert ret == pytest.approx(0.02)
    # window bars 0..1 → lowest low = 98
    assert mae == pytest.approx((98 - 100) / 100)


def test_score_intraday_no_data_yet():
    idx = pd.date_range("2026-07-06 09:15", periods=1, freq="60min", tz="UTC")
    df = pd.DataFrame({"Open": [100], "High": [101], "Low": [99], "Close": [100]}, index=idx)
    sig_ts = datetime(2026, 7, 6, 9, 15, tzinfo=UTC)
    # no bar exists at/after 10:15 yet
    assert SignalLedgerService._score_intraday(df, sig_ts, 100, "long") is None


# ── Stats aggregation ─────────────────────────────────────────────────────
def test_build_stats_hit_rate_and_return():
    rows = [
        {"signal_id": 1, "regime": "trending", "confidence": 70, "horizon": "1d", "return_pct": 0.02, "hit": 1},
        {"signal_id": 2, "regime": "trending", "confidence": 70, "horizon": "1d", "return_pct": -0.01, "hit": 0},
        {"signal_id": 3, "regime": "range_bound", "confidence": 40, "horizon": "1d", "return_pct": 0.03, "hit": 1},
    ]
    stats = build_stats(rows)
    assert stats["total_signals"] == 3
    assert stats["overall"]["1d"]["evaluated"] == 3
    assert stats["overall"]["1d"]["hit_rate"] == pytest.approx(66.7, abs=0.1)
    # avg of 2%, -1%, 3% = 1.33%
    assert stats["overall"]["1d"]["avg_return_pct"] == pytest.approx(1.33, abs=0.01)
    assert stats["by_regime"]["trending"]["1d"]["hit_rate"] == 50.0
    assert stats["by_confidence_bucket"]["65-80"]["1d"]["evaluated"] == 2


def test_build_stats_neutral_excluded_from_hit_rate():
    rows = [
        {"signal_id": 1, "regime": "range_bound", "confidence": 45, "horizon": "1h", "return_pct": 0.01, "hit": None},
    ]
    stats = build_stats(rows)
    # counted for return, but hit_rate has 0 hits / 1 evaluated = 0.0
    assert stats["overall"]["1h"]["evaluated"] == 1
    assert stats["overall"]["1h"]["hit_rate"] == 0.0
    assert stats["overall"]["1h"]["avg_return_pct"] == pytest.approx(1.0)


# ── Append-only structure + repo roundtrip ────────────────────────────────
def test_ledger_repo_has_no_mutation_methods():
    names = [n for n in dir(SignalRepository) if not n.startswith("_")]
    for n in names:
        low = n.lower()
        assert "update" not in low, f"ledger repo exposes a mutation method: {n}"
        assert "delete" not in low, f"ledger repo exposes a delete method: {n}"


@pytest.fixture
def signal_tables():
    SignalRepository.init_signal_ledger_db()
    from conftest import _test_db_conn
    _test_db_conn.execute("DELETE FROM signal_outcomes")
    _test_db_conn.execute("DELETE FROM signal_ledger")
    _test_db_conn.commit()
    yield


def _sample_signal():
    return {
        "signal_ts": "2026-07-06T09:20:00+00:00", "scan_id": "scan_1",
        "symbol": "RELIANCE.NS", "direction": "long", "confidence": 70,
        "regime": "trending", "indicator_states": {"macd": "BULLISH"},
        "sentiment_score": 58.0, "entry_price": 100.0, "adx": 30.0,
        "rsi": 55.0, "volatility": 1.5, "model_version": "consensus_v1.0",
        "corrects_signal_id": None, "raw_prediction": {"x": 1},
    }


def test_insert_and_outcome_write_once(signal_tables):
    sid = SignalRepository.insert_signal(_sample_signal())
    assert sid is not None

    # First outcome write succeeds and is reflected in the join.
    assert SignalRepository.record_outcome(sid, "1d", "2026-07-07T12:00:00+00:00", 105.0, 0.05, 1, -0.03)
    # Second write for the same (signal, horizon) is ignored (write-once).
    SignalRepository.record_outcome(sid, "1d", "2026-07-07T12:00:00+00:00", 999.0, 9.99, 0, -9.0)

    rows = SignalRepository._fetch_joined(ticker="RELIANCE")
    scored = [r for r in rows if r["horizon"] == "1d"]
    assert len(scored) == 1
    assert scored[0]["exit_price"] == 105.0     # not overwritten by the 999 attempt
    assert scored[0]["return_pct"] == pytest.approx(0.05)


def test_pending_scoring_excludes_fully_scored(signal_tables):
    sid = SignalRepository.insert_signal(_sample_signal())
    for h in HORIZONS:
        SignalRepository.record_outcome(sid, h, "2026-07-09T12:00:00+00:00", 105.0, 0.05, 1, -0.01)
    pending = SignalRepository.get_signals_pending_scoring(within_days=3650)
    assert all(p["signal_id"] != sid for p in pending)
