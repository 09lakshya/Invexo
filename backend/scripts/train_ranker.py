"""
Trains the cross-sectional Daily Edge ranker.

Instead of one regressor per stock (which had median R^2 of -0.43 — worse
than guessing), this trains ONE XGBoost classifier across the whole
universe pooled together, predicting the probability that a stock's
forward return beats the cross-sectional median ("outperforms the
market"). Two models are trained: a 1-day and a 5-day horizon.

Validation is walk-forward (train on past, test on strictly later dates)
and reports the metrics that matter for a picks product:
  - AUC (rank quality)
  - hit rate of the daily top-10 picks (did they beat the median?)
  - avg forward return of daily top-10 vs the universe average (the edge)

Usage:
  python scripts/train_ranker.py            # train + walk-forward report
  python scripts/train_ranker.py --refresh  # ignore cached price data
"""

import os
import sys
import json
import time
import argparse
import pickle

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.market.universe import FULL_UNIVERSE
from app.services.ai.ranker_features import (
    RANKER_FEATURES, compute_symbol_features, build_cross_section,
)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.environ.get("RENDER_DISK_PATH", os.path.join(BACKEND_DIR, "models"))
CACHE_DIR = os.path.join(BACKEND_DIR, "data_cache")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

HISTORY_PERIOD = "5y"
CHUNK_SIZE = 40
TOP_K = 10  # daily picks evaluated in the walk-forward report

# Label thresholds: what counts as a "winner" per horizon.
# 1d: beat the daily median (dense signal). 5d: land in the top 30% of
# 5-day performers — sharper label that focuses the model on the tail
# we actually pick from.
LABEL_QUANTILE = {"1d": 0.5, "5d": 0.7}


def download_universe(refresh: bool = False) -> dict:
    """Batch-download OHLCV history for the universe. Returns {symbol: df}."""
    cache_path = os.path.join(CACHE_DIR, "ranker_prices.pkl")
    if not refresh and os.path.exists(cache_path):
        age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600
        if age_hours < 20:
            print(f"Using cached price data ({age_hours:.1f}h old): {cache_path}")
            with open(cache_path, "rb") as f:
                return pickle.load(f)

    import yfinance as yf

    data = {}
    chunks = [FULL_UNIVERSE[i:i + CHUNK_SIZE] for i in range(0, len(FULL_UNIVERSE), CHUNK_SIZE)]
    for ci, chunk in enumerate(chunks):
        print(f"Downloading chunk {ci + 1}/{len(chunks)} ({len(chunk)} tickers)...")
        try:
            raw = yf.download(
                tickers=" ".join(chunk),
                period=HISTORY_PERIOD,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception as e:
            print(f"  chunk download failed: {e}")
            continue

        for sym in chunk:
            try:
                df = raw[sym].dropna(subset=["Close"]) if isinstance(raw.columns, pd.MultiIndex) else raw.dropna(subset=["Close"])
                if len(df) >= 100:
                    data[sym] = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            except Exception:
                continue
        time.sleep(1.0)

    print(f"Downloaded usable history for {len(data)}/{len(FULL_UNIVERSE)} symbols")
    with open(cache_path, "wb") as f:
        pickle.dump(data, f)
    return data


def build_dataset(price_data: dict) -> pd.DataFrame:
    """Build the pooled cross-sectional dataset with forward-return labels."""
    feats = {}
    for sym, df in price_data.items():
        f = compute_symbol_features(df)
        if f is not None:
            feats[sym] = f

    panel = build_cross_section(feats)
    if panel.empty:
        raise RuntimeError("No usable data after feature engineering")

    # Forward returns per symbol (shift within each symbol's own series)
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)
    g = panel.groupby("symbol")["Close"]
    panel["fwd_ret_1d"] = g.shift(-1) / panel["Close"] - 1
    panel["fwd_ret_5d"] = g.shift(-5) / panel["Close"] - 1

    # Labels: beat the cross-sectional quantile threshold that date
    for h in ("1d", "5d"):
        q = LABEL_QUANTILE[h]
        thresh = panel.groupby("date")[f"fwd_ret_{h}"].transform(lambda s: s.quantile(q))
        panel[f"label_{h}"] = (panel[f"fwd_ret_{h}"] > thresh).astype(int)
        # rows where fwd return itself is NaN are unusable for this horizon
        panel.loc[panel[f"fwd_ret_{h}"].isna(), f"label_{h}"] = np.nan

    return panel


def make_model() -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        objective="binary:logistic",
        n_estimators=350,
        learning_rate=0.05,
        max_depth=4,
        min_child_weight=50,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=2.0,
        eval_metric="auc",
        random_state=42,
        n_jobs=-1,
    )


def walk_forward_eval(panel: pd.DataFrame, horizon: str, n_folds: int = 4) -> dict:
    """Expanding-window walk-forward validation. Test data is always
    strictly later in time than training data."""
    label_col = f"label_{horizon}"
    ret_col = f"fwd_ret_{horizon}"
    df = panel.dropna(subset=[label_col]).copy()
    dates = np.array(sorted(df["date"].unique()))

    # First 55% is the minimum train window; remaining 45% split into folds
    start_idx = int(len(dates) * 0.55)
    fold_bounds = np.linspace(start_idx, len(dates), n_folds + 1, dtype=int)

    aucs, hit_rates, edges, abs_wins = [], [], [], []
    for i in range(n_folds):
        train_dates = dates[:fold_bounds[i]]
        test_dates = dates[fold_bounds[i]:fold_bounds[i + 1]]
        if len(test_dates) == 0:
            continue

        train = df[df["date"].isin(train_dates)]
        test = df[df["date"].isin(test_dates)]

        model = make_model()
        model.fit(train[RANKER_FEATURES], train[label_col].astype(int), verbose=False)
        probs = model.predict_proba(test[RANKER_FEATURES])[:, 1]
        test = test.assign(prob=probs)

        aucs.append(roc_auc_score(test[label_col].astype(int), probs))

        # Daily top-K evaluation
        daily_hits, daily_edges, daily_abs_wins = [], [], []
        for _, day in test.groupby("date"):
            if len(day) < TOP_K * 2:
                continue
            top = day.nlargest(TOP_K, "prob")
            daily_hits.append(top[label_col].mean())
            daily_edges.append(top[ret_col].mean() - day[ret_col].mean())
            daily_abs_wins.append((top[ret_col] > 0).mean())
        if daily_hits:
            hit_rates.append(float(np.mean(daily_hits)))
            edges.append(float(np.mean(daily_edges)))
            abs_wins.append(float(np.mean(daily_abs_wins)))

    base_rate = float(df[label_col].mean())
    return {
        "auc": round(float(np.mean(aucs)), 4) if aucs else None,
        "top10_label_hit_rate": round(float(np.mean(hit_rates)), 4) if hit_rates else None,
        "label_base_rate": round(base_rate, 4),
        "top10_abs_win_rate": round(float(np.mean(abs_wins)), 4) if abs_wins else None,
        "top10_daily_edge_pct": round(float(np.mean(edges)) * 100, 4) if edges else None,
        "folds": n_folds,
    }


def train_final(panel: pd.DataFrame, horizon: str) -> xgb.XGBClassifier:
    label_col = f"label_{horizon}"
    df = panel.dropna(subset=[label_col])
    model = make_model()
    model.fit(df[RANKER_FEATURES], df[label_col].astype(int), verbose=False)
    return model


def main():
    parser = argparse.ArgumentParser(description="Train the Daily Edge cross-sectional ranker")
    parser.add_argument("--refresh", action="store_true", help="Ignore cached price data")
    args = parser.parse_args()

    t0 = time.time()
    price_data = download_universe(refresh=args.refresh)
    panel = build_dataset(price_data)
    n_dates = panel["date"].nunique()
    print(f"\nDataset: {len(panel):,} rows | {panel['symbol'].nunique()} symbols | {n_dates} dates")

    meta = {
        "features": RANKER_FEATURES,
        "symbols": int(panel["symbol"].nunique()),
        "rows": int(len(panel)),
        "trained_at": pd.Timestamp.now().isoformat(),
        "metrics": {},
    }

    for horizon in ("1d", "5d"):
        print(f"\n=== Horizon: {horizon} ===")
        metrics = walk_forward_eval(panel, horizon)
        print(f"Walk-forward AUC:        {metrics['auc']}")
        print(f"Top-{TOP_K} label hit rate:  {metrics['top10_label_hit_rate']} (base rate {metrics['label_base_rate']})")
        print(f"Top-{TOP_K} abs win rate:    {metrics['top10_abs_win_rate']}")
        print(f"Top-{TOP_K} daily edge:      {metrics['top10_daily_edge_pct']}% vs universe avg")
        meta["metrics"][horizon] = metrics

        model = train_final(panel, horizon)
        path = os.path.join(MODELS_DIR, f"ranker_{horizon}.json")
        model.save_model(path)
        print(f"Saved {path}")

    with open(os.path.join(MODELS_DIR, "ranker_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nDone in {time.time() - t0:.0f}s. Meta saved to models/ranker_meta.json")


if __name__ == "__main__":
    main()
