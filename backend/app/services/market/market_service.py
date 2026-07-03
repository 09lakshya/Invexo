import os
import json
from datetime import datetime
from app.repositories.picks_repository import PicksRepository
from app.services.market.universe import (
    LARGE_CAP_UNIVERSE, MID_CAP_UNIVERSE, SMALL_CAP_UNIVERSE,
)
from app.utils.logger import get_logger

logger = get_logger("market_service")

# How many picks per cap bucket, and the minimum edge a stock needs to
# qualify: lift_5d is the stock's probability of being a top-30% 5-day
# performer relative to the average stock (1.0 = average).
PICKS_PER_BUCKET = 6
MIN_LIFT_5D = 1.10


class MarketService:
    @staticmethod
    def get_today_date_str() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def get_daily_picks():
        today = MarketService.get_today_date_str()
        return PicksRepository.get_daily_picks(today)

    @staticmethod
    def _signal_1d(prob: float) -> str:
        if prob >= 0.55:
            return "Bullish"
        if prob <= 0.45:
            return "Bearish"
        return "Neutral"

    @staticmethod
    def _build_pick(row: dict) -> dict:
        """Convert a ranker score row into the pick payload the UI shows."""
        prob_5d = row["prob_5d"]
        lift_5d = row["lift_5d"]
        expected_5d = row["expected_5d_pct"]
        target_price = round(row["close"] * (1 + expected_5d / 100), 2)
        return {
            "symbol": row["symbol"].replace(".NS", "").replace(".BO", ""),
            "full_symbol": row["symbol"],
            "cap": row["cap"],
            "current_price": row["close"],
            "target_price": target_price,
            "upside": expected_5d,                    # expected 5d move, %
            "expected_5d_pct": expected_5d,
            "prob_5d": prob_5d,
            "prob_1d": row["prob_1d"],
            "lift_5d": lift_5d,                       # x-times avg stock
            "lift_1d": row["lift_1d"],
            "signal_1d": MarketService._signal_1d(row["prob_1d"]),
            "confidence": round(prob_5d * 100, 1),    # model probability as %
            "score": round(lift_5d * 100, 1),
            "momentum_21d_pct": row.get("momentum_21d_pct"),
            "rsi_14": row.get("rsi_14"),
            "daily_vol_pct": row.get("daily_vol_pct"),
            "reasoning": (
                f"The cross-sectional model rates {row['symbol'].replace('.NS', '')} "
                f"{lift_5d}x more likely than the average stock to be a top 5-day performer "
                f"(21-day momentum {row.get('momentum_21d_pct', 0):+.1f}%, RSI {row.get('rsi_14', 50):.0f})."
            ),
        }

    @staticmethod
    def generate_daily_picks(force=False):
        today = MarketService.get_today_date_str()
        import tempfile
        lock_file = os.path.join(tempfile.gettempdir(), f"invexo_picks_{today}.lock")
        if not force:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, b"locked")
                os.close(fd)
            except FileExistsError:
                logger.warning(f"Another worker is already generating picks for {today}. Skipping.")
                return

        existing = MarketService.get_daily_picks()
        if existing is not None and not force:
            # v2 payloads carry a "model" marker; anything else is legacy → regenerate
            if isinstance(existing, dict) and existing.get("model") == "ranker_v2":
                logger.info(f"Valid ranker picks already exist for {today}. Skipping.")
                return
            logger.info(f"Legacy picks found for {today}. Regenerating with ranker.")

        logger.info(f"Starting Daily Edge ranker screening for {today}...")
        from app.services.ai.ranker_service import RankerService, get_ranker_meta

        scores = RankerService.score_universe()
        if not scores:
            logger.error("Ranker returned no scores; daily picks not generated.")
            return

        buckets = {"large_cap": [], "mid_cap": [], "small_cap": []}
        for row in sorted(scores, key=lambda r: r["lift_5d"], reverse=True):
            bucket = buckets.get(row["cap"])
            if bucket is None or len(bucket) >= PICKS_PER_BUCKET:
                continue
            if row["lift_5d"] < MIN_LIFT_5D:
                continue
            bucket.append(MarketService._build_pick(row))

        meta = get_ranker_meta() or {}
        as_of = scores[0].get("as_of") if scores else today
        final_picks = {
            "model": "ranker_v2",
            "generated_at": datetime.now().isoformat(),
            "as_of": as_of,
            "horizons": ["1d", "5d"],
            "universe_size": len(scores),
            "model_metrics": meta.get("metrics", {}),
            "large_cap": buckets["large_cap"],
            "mid_cap": buckets["mid_cap"],
            "small_cap": buckets["small_cap"],
        }

        PicksRepository.save_daily_picks(today, json.dumps(final_picks))
        all_picks = buckets["large_cap"] + buckets["mid_cap"] + buckets["small_cap"]
        PicksRepository.record_pick_outcomes(today, all_picks)
        logger.info(
            f"Saved ranker picks for {today}: "
            f"{len(buckets['large_cap'])} large, {len(buckets['mid_cap'])} mid, "
            f"{len(buckets['small_cap'])} small (universe scored: {len(scores)})"
        )

    @staticmethod
    def evaluate_pick_outcomes():
        """Fill realized 1d/5d returns for past picks. Run daily after close.

        A pick's 1d outcome uses the first close AFTER the pick date; the 5d
        outcome uses the fifth close after. Evaluation is idempotent — each
        outcome is written once.
        """
        pending = PicksRepository.get_pending_outcomes()
        if not pending:
            return

        symbols = sorted({p["symbol"] for p in pending})
        logger.info(f"Evaluating outcomes for {len(pending)} picks across {len(symbols)} symbols...")

        import yfinance as yf
        import pandas as pd
        from app.services.market.ticker_utils import _yf_session

        try:
            raw = yf.download(
                tickers=" ".join(symbols),
                period="3mo",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=False,
                progress=False,
                session=_yf_session,
            )
        except Exception as e:
            logger.error(f"Outcome evaluation download failed: {e}")
            return

        filled = 0
        for p in pending:
            try:
                sym = p["symbol"]
                df = raw[sym] if isinstance(raw.columns, pd.MultiIndex) else raw
                closes = df["Close"].dropna()
                if closes.empty:
                    continue
                idx = pd.to_datetime(closes.index)
                if idx.tz is not None:
                    idx = idx.tz_localize(None)
                idx_dates = [d.date() for d in idx]
                pick_date = pd.Timestamp(p["pick_date"]).date()
                # positions strictly after the pick date
                after = [i for i, d in enumerate(idx_dates) if d > pick_date]
                if not after:
                    continue
                entry = float(p["entry_price"])
                if p.get("ret_1d") is None and len(after) >= 1:
                    ret = float(closes.iloc[after[0]]) / entry - 1
                    PicksRepository.fill_outcome(p["id"], "1d", round(ret, 5))
                    filled += 1
                if p.get("ret_5d") is None and len(after) >= 5:
                    ret = float(closes.iloc[after[4]]) / entry - 1
                    PicksRepository.fill_outcome(p["id"], "5d", round(ret, 5))
                    filled += 1
            except Exception as e:
                logger.error(f"Outcome eval error for {p.get('symbol')}: {e}")

        logger.info(f"Filled {filled} pick outcomes.")
