"""
Shared feature engineering for the cross-sectional Daily Edge ranker.

Used by both scripts/train_ranker.py (training) and ranker_service.py
(inference) so features are guaranteed identical in both paths.

The model consumes cross-sectional percentile ranks: each feature is
ranked across all stocks per date, so the model learns "which stocks look
strongest *relative to the market today*" — far more stationary than raw
per-stock values.
"""

import numpy as np
import pandas as pd

# Feature columns fed to the model, in training order.
# *_rank features are cross-sectional percentile ranks in [0, 1].
# mkt_* / breadth are date-level regime features (same for all stocks that day).
RANKER_FEATURES = [
    "ret_1d_rank", "ret_5d_rank", "ret_21d_rank", "ret_63d_rank", "ret_126d_rank",
    "vol_21d_rank", "vol_63d_rank", "rsi_14_rank", "macd_hist_rank", "vol_ratio_rank",
    "dist_high_63_rank", "dist_low_63_rank", "bb_pos_rank",
    "ma20_gap_rank", "ma50_gap_rank",
    "rsi_14", "bb_pos", "vol_21d",
    "mkt_ret_5d", "mkt_ret_21d", "breadth_ma50",
]

# Raw per-symbol features that get rank-transformed per date
_RANKABLE = [
    "ret_1d", "ret_5d", "ret_21d", "ret_63d", "ret_126d",
    "vol_21d", "vol_63d", "rsi_14", "macd_hist", "vol_ratio",
    "dist_high_63", "dist_low_63", "bb_pos",
    "ma20_gap", "ma50_gap",
]

MIN_HISTORY_ROWS = 140  # rows of OHLCV needed before features are valid


def compute_symbol_features(df: pd.DataFrame) -> pd.DataFrame | None:
    """Compute time-series features for one symbol.

    df: OHLCV DataFrame indexed by date with Close and Volume columns.
    Returns a DataFrame indexed like df with raw feature columns, or None
    if there is not enough history.
    """
    if df is None or len(df) < MIN_HISTORY_ROWS:
        return None

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float).replace(0, np.nan)

    out = pd.DataFrame(index=df.index)

    # Momentum
    out["ret_1d"] = close.pct_change(1)
    out["ret_5d"] = close.pct_change(5)
    out["ret_21d"] = close.pct_change(21)
    out["ret_63d"] = close.pct_change(63)
    out["ret_126d"] = close.pct_change(126)

    # Volatility (annualization unnecessary — ranks are scale-free)
    out["vol_21d"] = close.pct_change().rolling(21).std()
    out["vol_63d"] = close.pct_change().rolling(63).std()

    # RSI-14 (Wilder smoothing)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi_14"] = 100 - 100 / (1 + rs)

    # MACD histogram normalized by price (comparable across stocks)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    out["macd_hist"] = (macd - signal) / close

    # Volume surge vs 20d average. Yahoo occasionally reports Volume=0 for
    # NSE days (bad data); those are NaN here, so the rolling mean skips
    # them (min_periods) and a missing current-day volume falls back to a
    # neutral ratio of 1 instead of poisoning the row.
    vol_avg = volume.rolling(20, min_periods=10).mean()
    out["vol_ratio"] = (volume / vol_avg).fillna(1.0)

    # Distance from 63d high / low
    out["dist_high_63"] = close / close.rolling(63).max() - 1
    out["dist_low_63"] = close / close.rolling(63).min() - 1

    # Bollinger position: -1 (lower band) .. +1 (upper band)
    ma20 = close.rolling(20).mean()
    sd20 = close.rolling(20).std()
    band_width = (4 * sd20).replace(0, np.nan)
    out["bb_pos"] = ((close - ma20) / band_width).clip(-1.5, 1.5)

    # Gap to moving averages
    out["ma20_gap"] = close / ma20 - 1
    out["ma50_gap"] = close / close.rolling(50).mean() - 1

    out["Close"] = close
    return out


def build_cross_section(feature_frames: dict) -> pd.DataFrame:
    """Stack per-symbol feature frames and add per-date percentile ranks.

    feature_frames: {symbol: DataFrame from compute_symbol_features}
    Returns a long DataFrame with columns [date, symbol, <raw>, <rank>, Close].
    """
    frames = []
    for symbol, feats in feature_frames.items():
        if feats is None or feats.empty:
            continue
        f = feats.copy()
        f["symbol"] = symbol
        f["date"] = f.index
        # Normalize away timezone so dates group correctly across symbols
        f["date"] = pd.to_datetime(f["date"]).dt.tz_localize(None).dt.normalize()
        frames.append(f)

    if not frames:
        return pd.DataFrame()

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.dropna(subset=_RANKABLE)

    for col in _RANKABLE:
        panel[f"{col}_rank"] = panel.groupby("date")[col].rank(pct=True)

    # Market-regime features (identical for all stocks on a given date):
    # recent breadth-weighted market direction so the model can condition
    # its stock ranking on the environment it's ranking in.
    by_date = panel.groupby("date")
    panel["mkt_ret_5d"] = by_date["ret_5d"].transform("mean")
    panel["mkt_ret_21d"] = by_date["ret_21d"].transform("mean")
    panel["breadth_ma50"] = by_date["ma50_gap"].transform(lambda s: (s > 0).mean())

    return panel
