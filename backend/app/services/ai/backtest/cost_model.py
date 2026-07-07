"""
Realistic cost model for NSE equity trades (Phase 2).

Every component is a configurable rate with a conservative default, and each is
documented here so the assumptions are auditable. Defaults model a *delivery*
(multi-day hold) trade. Shorts are modelled symmetrically with the same
delivery cost structure — a conservative (higher-cost) simplification, since
true overnight shorting in India requires SLB.

These functions decide realized net P&L, so they are pure and unit-tested
(tests/test_backtest.py).

Charge references (India, equity delivery, as configured — verify against your
broker's contract note):
  - Brokerage      : per-order, min(rate × turnover, cap). Default 0.03%, ₹20 cap.
  - STT            : 0.10% of turnover on BOTH buy and sell (delivery).
  - Exchange txn   : NSE ≈ 0.00297% of turnover, both sides.
  - SEBI charges   : ₹10 per crore = 0.0001% of turnover, both sides.
  - GST            : 18% on (brokerage + exchange txn + SEBI).
  - Stamp duty     : 0.015% of turnover, BUY side only.
  - Slippage       : configurable adverse price move per side. Default 10 bps.
"""

from dataclasses import dataclass, asdict, fields


@dataclass
class CostModel:
    # All rates are fractions of turnover unless noted.
    brokerage_rate: float = 0.0003        # 0.03% per order
    brokerage_cap: float = 20.0           # ₹ per order
    stt_rate: float = 0.001               # 0.10% both sides (delivery)
    exchange_txn_rate: float = 0.0000297  # NSE 0.00297%
    sebi_rate: float = 0.000001           # ₹10 / crore
    gst_rate: float = 0.18                # on brokerage+exchange+sebi
    stamp_rate: float = 0.00015           # 0.015%, buy side only
    slippage_bps: float = 10.0            # per side, basis points

    # ── Slippage ──────────────────────────────────────────────────────
    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / 10000.0

    def fill_price(self, price: float, action: str) -> float:
        """Adverse-fill price: a buy fills higher, a sell fills lower."""
        if action == "buy":
            return price * (1 + self.slippage_rate)
        if action == "sell":
            return price * (1 - self.slippage_rate)
        raise ValueError("action must be 'buy' or 'sell'")

    # ── Statutory + brokerage charges for one order ───────────────────
    def _one_side(self, turnover: float, action: str) -> dict:
        turnover = abs(turnover)
        brokerage = min(self.brokerage_rate * turnover, self.brokerage_cap)
        exchange = self.exchange_txn_rate * turnover
        sebi = self.sebi_rate * turnover
        gst = self.gst_rate * (brokerage + exchange + sebi)
        stt = self.stt_rate * turnover
        stamp = self.stamp_rate * turnover if action == "buy" else 0.0
        total = brokerage + exchange + sebi + gst + stt + stamp
        return {
            "brokerage": brokerage, "exchange_txn": exchange, "sebi": sebi,
            "gst": gst, "stt": stt, "stamp_duty": stamp, "total": total,
        }

    def round_trip_charges(self, buy_turnover: float, sell_turnover: float) -> dict:
        """Total statutory + brokerage charges for a round trip. Slippage is
        NOT included here (it is applied to fill prices via fill_price)."""
        buy = self._one_side(buy_turnover, "buy")
        sell = self._one_side(sell_turnover, "sell")
        breakdown = {k: round(buy[k] + sell[k], 4) for k in buy}
        return {"buy": buy, "sell": sell, **breakdown}

    # ── Config helpers ────────────────────────────────────────────────
    def to_dict(self) -> dict:
        d = asdict(self)
        d["slippage_rate"] = self.slippage_rate
        return d

    @classmethod
    def from_overrides(cls, overrides: dict | None) -> "CostModel":
        """Build a CostModel, applying only recognised, validated overrides."""
        if not overrides:
            return cls()
        allowed = {f.name for f in fields(cls)}
        clean = {}
        for k, v in overrides.items():
            if k in allowed and v is not None:
                fv = float(v)
                if fv < 0:
                    raise ValueError(f"Cost rate '{k}' must be non-negative")
                clean[k] = fv
        return cls(**clean)


def trade_pnl(entry_price: float, exit_price: float, qty: float,
              direction: str, cost: CostModel) -> dict:
    """Net P&L (₹) of one round-trip trade, direction-aware, after slippage
    and all statutory charges. Pure — the core money math for the backtest.

    - long : buy at entry (fills higher), sell at exit (fills lower)
    - short: sell at entry (fills lower), buy at exit (fills higher)
    """
    if qty <= 0 or entry_price <= 0 or exit_price <= 0:
        raise ValueError("qty and prices must be positive")
    if direction == "long":
        entry_fill = cost.fill_price(entry_price, "buy")
        exit_fill = cost.fill_price(exit_price, "sell")
        gross = qty * (exit_fill - entry_fill)
        buy_turnover, sell_turnover = qty * entry_fill, qty * exit_fill
    elif direction == "short":
        entry_fill = cost.fill_price(entry_price, "sell")
        exit_fill = cost.fill_price(exit_price, "buy")
        gross = qty * (entry_fill - exit_fill)
        buy_turnover, sell_turnover = qty * exit_fill, qty * entry_fill
    else:
        raise ValueError("direction must be 'long' or 'short'")

    charges = cost.round_trip_charges(buy_turnover, sell_turnover)
    net = gross - charges["total"]
    notional = qty * entry_fill
    return {
        "entry_fill": round(entry_fill, 4),
        "exit_fill": round(exit_fill, 4),
        "gross_pnl": round(gross, 4),
        "charges": round(charges["total"], 4),
        "net_pnl": round(net, 4),
        "notional": round(notional, 4),
        "net_return": net / notional if notional else 0.0,
    }
