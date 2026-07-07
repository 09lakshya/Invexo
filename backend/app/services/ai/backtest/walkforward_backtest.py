"""
Walk-forward backtest engine for the consensus predictor (Phase 2).

Design (all honest-by-construction):
  - Signals are the lookahead-safe historical consensus (historical_consensus).
  - A signal at the close of day t is acted on at the OPEN of t+1 (never the
    signal-day price) and held a fixed number of trading days, exit at close.
  - The only tunable knob (min-confidence threshold) is calibrated on each
    expanding TRAIN window and applied to the strictly-later TEST window; only
    out-of-sample trades feed the reported metrics — no in-sample results.
  - Every trade is charged the full CostModel (slippage + statutory charges).
  - Metrics always pair profitability with accuracy, and break out per regime.

Position sizing here is deliberately simple (fixed fraction of equity per
trade) — real risk-based sizing is Phase 4's job.
"""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from app.services.ai.backtest.cost_model import CostModel, trade_pnl
from app.services.ai.backtest.data_source import DataSource, YFinanceDataSource
from app.services.ai.backtest.historical_consensus import compute_consensus_frame
from app.utils.logger import get_logger

logger = get_logger("walkforward_backtest")

CONFIDENCE_GRID = [50, 60, 70, 80]
REFERENCE_NOTIONAL = 100000.0  # used only to rank thresholds in calibration


@dataclass
class BacktestConfig:
    symbols: list[str]
    start: str | None = None            # YYYY-MM-DD (signal window)
    end: str | None = None
    holding_days: int = 3
    initial_capital: float = 100000.0
    trade_fraction: float = 0.1         # fraction of equity risked per trade
    n_folds: int = 4
    period: str = "5y"                  # history depth to request
    cost_overrides: dict = field(default_factory=dict)


# ── Pure metric helpers (unit-tested) ─────────────────────────────────────

def profit_factor(net_pnls: list[float]) -> float | None:
    gains = sum(p for p in net_pnls if p > 0)
    losses = sum(-p for p in net_pnls if p < 0)
    if losses == 0:
        return None if gains == 0 else float("inf")
    return gains / losses


def max_drawdown(equity: list[float]) -> float:
    """Deepest peak-to-trough decline of the equity curve, as a fraction ≤ 0."""
    if not equity:
        return 0.0
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v / peak - 1)
    return mdd


def sharpe_ratio(returns: list[float], periods_per_year: float, rf: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    arr = np.array(returns, dtype=float) - rf
    sd = arr.std(ddof=1)
    if sd == 0:
        return None
    return float(arr.mean() / sd * np.sqrt(periods_per_year))


def sortino_ratio(returns: list[float], periods_per_year: float, rf: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    arr = np.array(returns, dtype=float) - rf
    downside = arr[arr < 0]
    if len(downside) == 0:
        return None
    dd = np.sqrt(np.mean(downside ** 2))
    if dd == 0:
        return None
    return float(arr.mean() / dd * np.sqrt(periods_per_year))


def cagr(initial: float, final: float, years: float) -> float | None:
    if initial <= 0 or final <= 0 or years <= 0:
        return None
    return (final / initial) ** (1 / years) - 1


# ── Engine ────────────────────────────────────────────────────────────────

class WalkForwardBacktest:
    def __init__(self, data_source: DataSource | None = None):
        self.ds = data_source or YFinanceDataSource()

    def _extract_trades(self, symbol: str, price: pd.DataFrame, holding_days: int,
                        start, end) -> list[dict]:
        """Non-overlapping candidate trades for one symbol."""
        sig = compute_consensus_frame(price)
        if sig.empty:
            return []
        idx = list(price.index)
        pos_of = {d: i for i, d in enumerate(idx)}
        trades = []
        last_exit_pos = -1
        for sig_date, row in sig.iterrows():
            if row["direction"] == "neutral":
                continue
            if start is not None and sig_date < start:
                continue
            if end is not None and sig_date > end:
                continue
            p = pos_of.get(sig_date)
            if p is None:
                continue
            entry_pos = p + 1
            exit_pos = p + holding_days
            if entry_pos <= last_exit_pos:        # still in a position
                continue
            if exit_pos >= len(idx):               # not enough future data
                continue
            trades.append({
                "symbol": symbol,
                "signal_date": sig_date,
                "entry_date": idx[entry_pos],
                "exit_date": idx[exit_pos],
                "direction": row["direction"],
                "confidence": int(row["confidence"]),
                "regime": row["regime"],
                "entry_price": float(price["Open"].iloc[entry_pos]),
                "exit_price": float(price["Close"].iloc[exit_pos]),
            })
            last_exit_pos = exit_pos
        return trades

    @staticmethod
    def _ref_return(trade: dict, cost: CostModel) -> float:
        qty = REFERENCE_NOTIONAL / trade["entry_price"]
        return trade_pnl(trade["entry_price"], trade["exit_price"], qty,
                         trade["direction"], cost)["net_return"]

    def _walk_forward_select(self, trades: list[dict], cost: CostModel,
                             n_folds: int) -> tuple[list[dict], list[dict]]:
        """Expanding-window threshold calibration. Returns (oos_trades, folds)."""
        if not trades:
            return [], []
        trades = sorted(trades, key=lambda t: t["signal_date"])
        for t in trades:
            t["_ref_ret"] = self._ref_return(t, cost)
        dates = sorted({t["signal_date"] for t in trades})
        if len(dates) < n_folds + 2:
            # Too few dates to walk forward — apply the most permissive
            # threshold to everything and mark it as a single degenerate fold.
            thr = CONFIDENCE_GRID[0]
            oos = [t for t in trades if t["confidence"] >= thr]
            return oos, [{"fold": 1, "threshold": thr, "trades": len(oos), "degenerate": True}]

        start_idx = int(len(dates) * 0.55)
        bounds = np.linspace(start_idx, len(dates), n_folds + 1, dtype=int)
        oos, folds = [], []
        for i in range(n_folds):
            train_dates = set(dates[:bounds[i]])
            test_dates = set(dates[bounds[i]:bounds[i + 1]])
            if not test_dates:
                continue
            train = [t for t in trades if t["signal_date"] in train_dates]
            test = [t for t in trades if t["signal_date"] in test_dates]

            best_thr, best_obj = CONFIDENCE_GRID[0], None
            for thr in CONFIDENCE_GRID:
                sel = [t["_ref_ret"] for t in train if t["confidence"] >= thr]
                if len(sel) < 5:
                    continue
                obj = float(np.mean(sel))   # best avg net return per trade in-sample
                if best_obj is None or obj > best_obj:
                    best_obj, best_thr = obj, thr

            fold_oos = [t for t in test if t["confidence"] >= best_thr]
            oos.extend(fold_oos)
            folds.append({"fold": i + 1, "threshold": best_thr,
                          "train_trades": len(train), "test_trades": len(fold_oos)})
        return oos, folds

    def _simulate(self, oos: list[dict], cfg: BacktestConfig, cost: CostModel) -> dict:
        """Sequential fixed-fractional equity simulation over OOS trades."""
        trades = sorted(oos, key=lambda t: t["exit_date"])
        equity = cfg.initial_capital
        curve = []          # [{date, equity}]
        net_returns = []    # per-trade net return (actual sizing)
        net_pnls = []
        enriched = []
        for t in trades:
            notional = cfg.trade_fraction * equity
            if notional <= 0:
                break
            qty = notional / t["entry_price"]
            pnl = trade_pnl(t["entry_price"], t["exit_price"], qty, t["direction"], cost)
            equity += pnl["net_pnl"]
            net_returns.append(pnl["net_return"])
            net_pnls.append(pnl["net_pnl"])
            curve.append({"date": t["exit_date"].strftime("%Y-%m-%d"), "equity": round(equity, 2)})
            enriched.append({**t, "net_pnl": pnl["net_pnl"], "net_return": pnl["net_return"]})

        return {"final_equity": equity, "curve": curve, "net_returns": net_returns,
                "net_pnls": net_pnls, "trades": enriched}

    @staticmethod
    def _regime_breakdown(trades: list[dict]) -> dict:
        out = {}
        by = {}
        for t in trades:
            by.setdefault(t["regime"], []).append(t)
        for regime, ts in by.items():
            rets = [t["net_return"] for t in ts]
            pnls = [t["net_pnl"] for t in ts]
            wins = [r for r in rets if r > 0]
            out[regime] = {
                "trades": len(ts),
                "win_rate": round(len(wins) / len(ts) * 100, 1) if ts else None,
                "avg_return_pct": round(float(np.mean(rets)) * 100, 2) if rets else None,
                "profit_factor": round(pf, 2) if (pf := profit_factor(pnls)) not in (None, float("inf")) else pf,
            }
        return out

    def run(self, cfg: BacktestConfig) -> dict:
        symbols = cfg.symbols[:40]
        cost = CostModel.from_overrides(cfg.cost_overrides)
        start = pd.Timestamp(cfg.start) if cfg.start else None
        end = pd.Timestamp(cfg.end) if cfg.end else None

        price_data = self.ds.get_history(symbols, period=cfg.period)
        warnings = []
        missing = [s for s in symbols if s not in price_data]
        if missing:
            warnings.append(f"No price data for: {', '.join(missing)}")

        all_trades = []
        for sym, df in price_data.items():
            all_trades.extend(self._extract_trades(sym, df, cfg.holding_days, start, end))

        if not all_trades:
            return {"error": "No trades generated for the given configuration.",
                    "config": self._echo(cfg), "cost_model": cost.to_dict(), "warnings": warnings}

        oos, folds = self._walk_forward_select(all_trades, cost, cfg.n_folds)
        if not oos:
            return {"error": "No out-of-sample trades after walk-forward selection.",
                    "config": self._echo(cfg), "cost_model": cost.to_dict(),
                    "folds": folds, "warnings": warnings}

        sim = self._simulate(oos, cfg, cost)
        metrics = self._metrics(sim, cfg)
        equity_curve = [{"date": cfg.start or "start", "equity": cfg.initial_capital}] + sim["curve"]
        drawdown_curve = self._drawdown_curve(equity_curve)

        return {
            "config": self._echo(cfg),
            "cost_model": cost.to_dict(),
            "n_signals": len(all_trades),
            "n_oos_trades": len(oos),
            "folds": folds,
            "metrics": metrics,
            "per_regime": self._regime_breakdown(sim["trades"]),
            "equity_curve": equity_curve,
            "drawdown_curve": drawdown_curve,
            "warnings": warnings,
        }

    # ── helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _echo(cfg: BacktestConfig) -> dict:
        return {"symbols": cfg.symbols, "start": cfg.start, "end": cfg.end,
                "holding_days": cfg.holding_days, "initial_capital": cfg.initial_capital,
                "trade_fraction": cfg.trade_fraction, "n_folds": cfg.n_folds,
                "confidence_grid": CONFIDENCE_GRID}

    def _metrics(self, sim: dict, cfg: BacktestConfig) -> dict:
        rets = sim["net_returns"]
        pnls = sim["net_pnls"]
        trades = sim["trades"]
        final = sim["final_equity"]
        n = len(trades)
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r < 0]

        first_entry = min(t["entry_date"] for t in trades)
        last_exit = max(t["exit_date"] for t in trades)
        years = max((last_exit - first_entry).days / 365.25, 1e-9)
        trades_per_year = n / years if years > 0 else 0.0

        equity_series = [cfg.initial_capital] + [p["equity"] for p in sim["curve"]]
        pf = profit_factor(pnls)
        return {
            "total_return_pct": round((final / cfg.initial_capital - 1) * 100, 2),
            "cagr_pct": round(c * 100, 2) if (c := cagr(cfg.initial_capital, final, years)) is not None else None,
            "sharpe": round(s, 2) if (s := sharpe_ratio(rets, trades_per_year)) is not None else None,
            "sortino": round(so, 2) if (so := sortino_ratio(rets, trades_per_year)) is not None else None,
            "max_drawdown_pct": round(max_drawdown(equity_series) * 100, 2),
            "profit_factor": round(pf, 2) if pf not in (None, float("inf")) else pf,
            "win_rate_pct": round(len(wins) / n * 100, 1) if n else None,
            "total_trades": n,
            "avg_win_pct": round(float(np.mean(wins)) * 100, 2) if wins else None,
            "avg_loss_pct": round(float(np.mean(losses)) * 100, 2) if losses else None,
            "avg_trade_pct": round(float(np.mean(rets)) * 100, 2) if rets else None,
            "trades_per_year": round(trades_per_year, 1),
            "final_equity": round(final, 2),
            "risk_note": "Sharpe/Sortino are trade-return based (annualised by trades/year), not daily MTM.",
        }

    @staticmethod
    def _drawdown_curve(equity_curve: list[dict]) -> list[dict]:
        peak = equity_curve[0]["equity"] if equity_curve else 0
        out = []
        for p in equity_curve:
            peak = max(peak, p["equity"])
            dd = (p["equity"] / peak - 1) * 100 if peak > 0 else 0.0
            out.append({"date": p["date"], "drawdown_pct": round(dd, 2)})
        return out
