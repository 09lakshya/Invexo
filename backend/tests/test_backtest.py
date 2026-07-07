"""
Tests for the Phase 2 backtest engine: cost model math, lookahead safety of
the historical consensus, trade P&L, and the reported metrics. These decide
whether a strategy looks profitable, so the math is pinned down directly.
"""

import numpy as np
import pandas as pd
import pytest

from app.services.ai.backtest.cost_model import CostModel, trade_pnl
from app.services.ai.backtest.historical_consensus import (
    compute_indicator_frame, compute_consensus_frame,
)
from app.services.ai.backtest.walkforward_backtest import (
    profit_factor, max_drawdown, sharpe_ratio, sortino_ratio, cagr,
    WalkForwardBacktest, BacktestConfig,
)


# ── Cost model ─────────────────────────────────────────────────────────────
def test_slippage_direction():
    c = CostModel(slippage_bps=10)  # 0.10%
    assert c.fill_price(100, "buy") == pytest.approx(100.10)
    assert c.fill_price(100, "sell") == pytest.approx(99.90)
    with pytest.raises(ValueError):
        c.fill_price(100, "hold")


def test_one_side_charges_known_values():
    c = CostModel()
    turnover = 100000.0  # ₹1,00,000 buy
    side = c._one_side(turnover, "buy")
    # brokerage = min(0.03% * 100000=30, cap 20) = 20
    assert side["brokerage"] == pytest.approx(20.0)
    # stt 0.1% = 100
    assert side["stt"] == pytest.approx(100.0)
    # exchange 0.00297% = 2.97
    assert side["exchange_txn"] == pytest.approx(2.97)
    # sebi 0.0001% = 0.1
    assert side["sebi"] == pytest.approx(0.1)
    # gst = 18% of (20 + 2.97 + 0.1) = 4.1526
    assert side["gst"] == pytest.approx(0.18 * (20 + 2.97 + 0.1))
    # stamp buy side 0.015% = 15
    assert side["stamp_duty"] == pytest.approx(15.0)
    expected_total = 20 + 100 + 2.97 + 0.1 + 0.18 * (20 + 2.97 + 0.1) + 15
    assert side["total"] == pytest.approx(expected_total)


def test_sell_side_has_no_stamp_duty():
    c = CostModel()
    assert c._one_side(100000.0, "sell")["stamp_duty"] == 0.0


def test_from_overrides_validates_and_filters():
    c = CostModel.from_overrides({"slippage_bps": 25, "unknown": 5, "stt_rate": None})
    assert c.slippage_bps == 25
    assert c.stt_rate == CostModel().stt_rate   # None ignored
    with pytest.raises(ValueError):
        CostModel.from_overrides({"stt_rate": -0.1})


# ── Trade P&L (direction-aware, after costs) ───────────────────────────────
def test_trade_pnl_long_profit_net_of_costs():
    c = CostModel(slippage_bps=0)  # isolate statutory charges
    r = trade_pnl(entry_price=100, exit_price=110, qty=100, direction="long", cost=c)
    # gross = 100 * (110 - 100) = 1000, minus charges → net < gross but > 0
    assert r["gross_pnl"] == pytest.approx(1000.0)
    assert r["net_pnl"] < r["gross_pnl"]
    assert r["net_pnl"] > 0
    assert r["net_return"] == pytest.approx(r["net_pnl"] / r["notional"])


def test_trade_pnl_short_profits_when_price_falls():
    c = CostModel(slippage_bps=0)
    r = trade_pnl(entry_price=100, exit_price=90, qty=100, direction="short", cost=c)
    assert r["gross_pnl"] == pytest.approx(1000.0)   # sold 100, covered 90
    assert r["net_pnl"] > 0


def test_trade_pnl_slippage_reduces_return():
    no_slip = trade_pnl(100, 110, 100, "long", CostModel(slippage_bps=0))
    with_slip = trade_pnl(100, 110, 100, "long", CostModel(slippage_bps=50))
    assert with_slip["net_pnl"] < no_slip["net_pnl"]


def test_trade_pnl_rejects_bad_input():
    c = CostModel()
    with pytest.raises(ValueError):
        trade_pnl(100, 110, 0, "long", c)
    with pytest.raises(ValueError):
        trade_pnl(100, 110, 10, "sideways", c)


# ── Lookahead safety of the historical consensus ───────────────────────────
def _synthetic_ohlcv(n=260, seed=7):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.015, n)
    close = 100 * np.cumprod(1 + rets)
    idx = pd.bdate_range("2023-01-02", periods=n)
    high = close * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.006, n)))
    openp = close * (1 + rng.normal(0, 0.004, n))
    vol = rng.integers(1e5, 1e6, n)
    return pd.DataFrame({"Open": openp, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def test_indicators_are_causal_no_lookahead():
    """Indicator value at day t must be identical whether computed on the full
    series or on the series truncated at t — the core anti-lookahead guarantee."""
    df = _synthetic_ohlcv()
    full = compute_indicator_frame(df)
    # check several interior points well past indicator warmup
    for t in (120, 180, 230):
        truncated = compute_indicator_frame(df.iloc[: t + 1])
        for col in ("rsi", "macd_diff", "ema9", "ema21", "adx", "stoch_k", "bb_middle"):
            a = full[col].iloc[t]
            b = truncated[col].iloc[t]
            assert a == pytest.approx(b, rel=1e-9, nan_ok=True), f"lookahead in {col} at t={t}"


def test_consensus_frame_has_expected_shape():
    df = _synthetic_ohlcv()
    frame = compute_consensus_frame(df)
    assert not frame.empty
    assert set(["direction", "confidence", "regime", "adx", "rsi"]).issubset(frame.columns)
    assert frame["direction"].isin(["long", "short", "neutral"]).all()
    assert frame["confidence"].between(35, 95).all()


# ── Metrics ────────────────────────────────────────────────────────────────
def test_profit_factor():
    assert profit_factor([100, -50, 50]) == pytest.approx(150 / 50)
    assert profit_factor([100, 50]) == float("inf")
    assert profit_factor([]) is None


def test_max_drawdown():
    # peak 120 → trough 90 = -25%
    eq = [100, 120, 90, 110]
    assert max_drawdown(eq) == pytest.approx(-0.25)
    assert max_drawdown([100, 110, 120]) == pytest.approx(0.0)


def test_sharpe_and_sortino_signs():
    rets = [0.02, -0.01, 0.03, 0.01, -0.005]
    s = sharpe_ratio(rets, periods_per_year=50)
    so = sortino_ratio(rets, periods_per_year=50)
    assert s is not None and s > 0
    assert so is not None and so > 0
    # sortino only penalises downside, so it should be >= sharpe here
    assert so >= s


def test_sharpe_none_on_zero_variance():
    assert sharpe_ratio([0.01, 0.01, 0.01], 50) is None
    assert sharpe_ratio([0.01], 50) is None


def test_cagr():
    assert cagr(100000, 121000, 2) == pytest.approx(0.10, abs=1e-6)  # doubled 10%/yr
    assert cagr(100000, 0, 2) is None
    assert cagr(100000, 121000, 0) is None


# ── End-to-end engine on synthetic data (no network) ───────────────────────
class _FakeDataSource:
    def __init__(self, data):
        self._data = data

    def get_history(self, symbols, period="5y"):
        return {s: self._data[s] for s in symbols if s in self._data}


def test_engine_runs_out_of_sample_and_reports_metrics():
    data = {"AAA.NS": _synthetic_ohlcv(seed=1), "BBB.NS": _synthetic_ohlcv(seed=2)}
    engine = WalkForwardBacktest(data_source=_FakeDataSource(data))
    cfg = BacktestConfig(symbols=["AAA.NS", "BBB.NS"], holding_days=3, n_folds=3)
    res = engine.run(cfg)
    assert "error" not in res, res.get("error")
    m = res["metrics"]
    # metrics present and internally consistent
    assert m["total_trades"] == res["n_oos_trades"]
    assert m["total_trades"] >= 1
    assert 0 <= m["win_rate_pct"] <= 100
    assert len(res["equity_curve"]) == m["total_trades"] + 1
    assert len(res["drawdown_curve"]) == len(res["equity_curve"])
    # every fold's threshold came from the calibration grid
    for f in res["folds"]:
        assert f["threshold"] in cfg.__dict__.get("confidence_grid", [50, 60, 70, 80]) or f["threshold"] in [50, 60, 70, 80]


def test_engine_no_lookahead_entry_after_signal():
    """Entry date must be strictly after the signal date for every trade."""
    data = {"AAA.NS": _synthetic_ohlcv(seed=3)}
    engine = WalkForwardBacktest(data_source=_FakeDataSource(data))
    trades = engine._extract_trades("AAA.NS", data["AAA.NS"], holding_days=3, start=None, end=None)
    assert trades
    for t in trades:
        assert t["entry_date"] > t["signal_date"], "entry must be after the signal bar"
        assert t["exit_date"] > t["entry_date"]
