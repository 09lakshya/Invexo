"""
Lookahead-safe historical replay of the consensus predictor's TECHNICAL vote
(Phase 2).

Reproduces the indicator-vote logic of PredictionService.predict_stock, but:
  - computed as-of each historical day (see below for why this is safe), and
  - with NLP sentiment and fundamentals held NEUTRAL, because we have no
    point-in-time archive of either; using today's values on a past bar would
    be lookahead. Their votes therefore contribute 0 to the trend score.

Why full-series computation is lookahead-safe: every indicator used here (RSI,
MACD, EMA, Bollinger, Stochastic, ADX) is *causal* — its value at bar t is a
function of bars ≤ t only. So computing the indicator over the whole series and
reading the value at t is identical to computing it on the truncated series
[:t]. tests/test_backtest.py asserts this equality directly.
"""

import numpy as np
import pandas as pd
import ta


def compute_indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Causal indicator columns aligned to df's index."""
    close = df["Close"]
    out = pd.DataFrame(index=df.index)
    out["Close"] = close
    out["rsi"] = ta.momentum.RSIIndicator(close=close, window=14).rsi()
    macd = ta.trend.MACD(close=close)
    out["macd_diff"] = macd.macd_diff()
    bb = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
    out["bb_middle"] = bb.bollinger_mavg()
    out["ema9"] = ta.trend.EMAIndicator(close=close, window=9).ema_indicator()
    out["ema21"] = ta.trend.EMAIndicator(close=close, window=21).ema_indicator()
    adx = ta.trend.ADXIndicator(high=df["High"], low=df["Low"], close=close, window=14)
    out["adx"] = adx.adx()
    out["plus_di"] = adx.adx_pos()
    out["minus_di"] = adx.adx_neg()
    stoch = ta.momentum.StochasticOscillator(high=df["High"], low=df["Low"], close=close, window=14, smooth_window=3)
    out["stoch_k"] = stoch.stoch()
    out["stoch_d"] = stoch.stoch_signal()
    out["volatility"] = close.pct_change().rolling(20).std()
    return out


def _row_signal(r) -> dict | None:
    """Consensus vote for a single day (mirrors predict_stock's technical
    portion; sentiment & fundamentals held NEUTRAL)."""
    if any(pd.isna(r[c]) for c in ("rsi", "macd_diff", "bb_middle", "ema9", "ema21", "adx", "stoch_k", "stoch_d")):
        return None

    rsi = float(r["rsi"])
    signals = {
        "ema_cross": "BULLISH" if r["ema9"] > r["ema21"] else "BEARISH",
        "macd": "BULLISH" if r["macd_diff"] > 0 else "BEARISH",
        "rsi": "BULLISH" if rsi < 35 or (35 <= rsi <= 65 and rsi > 50) else "BEARISH",
        "stochastic": "BULLISH" if r["stoch_k"] > r["stoch_d"] else "BEARISH",
        "bollinger": "BULLISH" if r["Close"] > r["bb_middle"] else "BEARISH",
        # sentiment & fundamentals unavailable historically → NEUTRAL (0 weight)
        "sentiment": "NEUTRAL",
        "fundamentals": "NEUTRAL",
    }

    score = 0.0
    score += 1.5 if signals["ema_cross"] == "BULLISH" else -1.5
    score += 1.5 if signals["macd"] == "BULLISH" else -1.5
    score += 1.0 if signals["rsi"] == "BULLISH" else -1.0
    score += 1.0 if signals["stochastic"] == "BULLISH" else -1.0
    score += 0.5 if signals["bollinger"] == "BULLISH" else -0.5

    adx = float(r["adx"])
    if adx > 25:
        if score > 0 and r["plus_di"] > r["minus_di"]:
            score += 1.0
        elif score < 0 and r["minus_di"] > r["plus_di"]:
            score -= 1.0

    trend = "BULLISH" if score > 0.5 else "BEARISH" if score < -0.5 else "NEUTRAL"
    non_neutral = [v for v in signals.values() if v != "NEUTRAL"]
    if trend != "NEUTRAL" and non_neutral:
        agree = sum(1 for v in non_neutral if v == trend)
        consensus_ratio = agree / len(non_neutral)
    else:
        consensus_ratio = 0.5

    vol = float(r["volatility"]) if not pd.isna(r["volatility"]) else 0.015
    base_conf = 50 + (consensus_ratio - 0.5) * 80
    adx_boost = min(10.0, (adx - 25) * 0.5) if adx > 25 else 0.0
    vol_penalty = min(10.0, vol * 150)
    # richness bonus (news/fundamentals source quality) is unavailable here → 0
    confidence = int(max(35, min(95, round(base_conf + adx_boost - vol_penalty))))

    direction = {"BULLISH": "long", "BEARISH": "short", "NEUTRAL": "neutral"}[trend]
    return {
        "direction": direction,
        "confidence": confidence,
        "regime": "trending" if adx > 25 else "range_bound",
        "adx": round(adx, 2),
        "rsi": round(rsi, 2),
    }


def compute_consensus_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Per-day consensus signal for a symbol. Returns a DataFrame indexed by
    date with direction/confidence/regime/adx/rsi (rows before indicators
    warm up are dropped)."""
    ind = compute_indicator_frame(df)
    records = []
    for ts, r in ind.iterrows():
        sig = _row_signal(r)
        if sig is None:
            continue
        sig["date"] = ts
        records.append(sig)
    if not records:
        return pd.DataFrame(columns=["date", "direction", "confidence", "regime", "adx", "rsi"])
    return pd.DataFrame.from_records(records).set_index("date")
