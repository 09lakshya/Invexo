"""
Inference for the cross-sectional Daily Edge ranker.

Loads the two pooled XGBoost classifiers (ranker_1d / ranker_5d) trained by
scripts/train_ranker.py and scores the whole universe in one pass:
batch-download recent history, compute the shared feature set, rank
cross-sectionally on the latest date, and predict outperformance
probabilities for both horizons.
"""

import os
import json
import time
import threading

import numpy as np
import pandas as pd
import xgboost as xgb

from app.services.market.universe import FULL_UNIVERSE, CAP_BY_SYMBOL
from app.services.ai.ranker_features import (
    RANKER_FEATURES, compute_symbol_features, build_cross_section,
)
from app.utils.logger import get_logger

logger = get_logger("ranker_service")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
MODELS_DIR = os.environ.get("RENDER_DISK_PATH", os.path.join(_BASE_DIR, "models"))

_lock = threading.Lock()
_models = {}
_meta = None

CHUNK_SIZE = 40

# Label base rates the classifiers were trained against (see
# LABEL_QUANTILE in scripts/train_ranker.py). A prediction equal to the
# base rate means "average stock"; probabilities are only meaningful
# relative to these. Actual values are read from ranker_meta.json.
DEFAULT_BASE_RATES = {"1d": 0.50, "5d": 0.30}


def _base_rates() -> dict:
    meta = _meta or {}
    rates = dict(DEFAULT_BASE_RATES)
    for h in ("1d", "5d"):
        br = (meta.get("metrics", {}).get(h) or {}).get("label_base_rate")
        if br:
            rates[h] = float(br)
    return rates


def _load_models():
    """Lazily load ranker models once per process."""
    global _models, _meta
    with _lock:
        if _models:
            return _models
        for horizon in ("1d", "5d"):
            path = os.path.join(MODELS_DIR, f"ranker_{horizon}.json")
            if not os.path.exists(path):
                logger.warning(f"Ranker model missing: {path}")
                continue
            try:
                model = xgb.XGBClassifier()
                model.load_model(path)
                _models[horizon] = model
            except Exception as e:
                logger.error(f"Failed to load ranker_{horizon}: {e}")
        meta_path = os.path.join(MODELS_DIR, "ranker_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    _meta = json.load(f)
            except Exception:
                _meta = None
        return _models


def get_ranker_meta() -> dict | None:
    _load_models()
    return _meta


def _download_recent(symbols: list) -> dict:
    """Batch-download ~1 year of daily OHLCV for feature computation
    (126-day momentum needs ≥140 rows of history)."""
    import yfinance as yf

    data = {}
    chunks = [symbols[i:i + CHUNK_SIZE] for i in range(0, len(symbols), CHUNK_SIZE)]
    for chunk in chunks:
        try:
            raw = yf.download(
                tickers=" ".join(chunk),
                period="1y",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception as e:
            logger.error(f"Ranker batch download failed: {e}")
            continue

        for sym in chunk:
            try:
                df = raw[sym].dropna(subset=["Close"]) if isinstance(raw.columns, pd.MultiIndex) else raw.dropna(subset=["Close"])
                if len(df) >= 140:
                    data[sym] = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            except Exception:
                continue
        time.sleep(0.5)
    return data


class RankerService:
    @staticmethod
    def score_universe() -> list[dict]:
        """Score the entire universe. Returns one dict per symbol with
        probabilities for both horizons and volatility-scaled expected moves.
        Empty list if models are missing or data fetch failed."""
        models = _load_models()
        if "1d" not in models or "5d" not in models:
            logger.error("Ranker models not available — run scripts/train_ranker.py")
            return []

        t0 = time.time()
        price_data = _download_recent(FULL_UNIVERSE)
        if len(price_data) < 50:
            logger.error(f"Ranker: only {len(price_data)} symbols downloaded; aborting scoring")
            return []

        feats = {}
        for sym, df in price_data.items():
            f = compute_symbol_features(df)
            if f is not None:
                feats[sym] = f

        panel = build_cross_section(feats)
        if panel.empty:
            logger.error("Ranker: empty feature panel")
            return []

        # Latest complete cross-section
        latest_date = panel["date"].max()
        snap = panel[panel["date"] == latest_date].copy()
        if len(snap) < 50:
            # thin last date (partial data) — fall back one day
            dates = sorted(panel["date"].unique())
            if len(dates) >= 2:
                latest_date = dates[-2]
                snap = panel[panel["date"] == latest_date].copy()

        X = snap[RANKER_FEATURES]
        snap["prob_1d"] = models["1d"].predict_proba(X)[:, 1]
        snap["prob_5d"] = models["5d"].predict_proba(X)[:, 1]

        base = _base_rates()
        results = []
        for _, row in snap.iterrows():
            sym = row["symbol"]
            daily_vol = float(row["vol_21d"]) if not np.isnan(row["vol_21d"]) else 0.015
            prob_1d = float(row["prob_1d"])
            prob_5d = float(row["prob_5d"])
            # Edge relative to the label base rate: 0 at "average stock",
            # 1 at certainty. Expected move = edge × the stock's own
            # volatility over the horizon — transparent and bounded.
            edge_1d = (prob_1d - base["1d"]) / (1 - base["1d"])
            edge_5d = (prob_5d - base["5d"]) / (1 - base["5d"])
            exp_1d = edge_1d * daily_vol
            exp_5d = edge_5d * daily_vol * np.sqrt(5)
            results.append({
                "symbol": sym,
                "cap": CAP_BY_SYMBOL.get(sym, "small_cap"),
                "close": round(float(row["Close"]), 2),
                "prob_1d": round(prob_1d, 4),
                "prob_5d": round(prob_5d, 4),
                # How many times more likely than the average stock
                "lift_1d": round(prob_1d / base["1d"], 2),
                "lift_5d": round(prob_5d / base["5d"], 2),
                "expected_1d_pct": round(exp_1d * 100, 2),
                "expected_5d_pct": round(exp_5d * 100, 2),
                "daily_vol_pct": round(daily_vol * 100, 2),
                "momentum_21d_pct": round(float(row["ret_21d"]) * 100, 2),
                "rsi_14": round(float(row["rsi_14"]), 1),
                "as_of": str(pd.Timestamp(latest_date).date()),
            })

        logger.info(
            f"Ranker scored {len(results)} symbols as of {pd.Timestamp(latest_date).date()} "
            f"in {time.time() - t0:.1f}s"
        )
        return results
