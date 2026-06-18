import os
import json
import concurrent.futures
from datetime import datetime
from app.repositories.picks_repository import PicksRepository
from app.services.ai.prediction_service import PredictionService
from app.utils.logger import get_logger

logger = get_logger("market_service")

# Universes for different market caps
LARGE_CAP_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "HINDUNILVR.NS", "BAJFINANCE.NS",
    "LT.NS", "KOTAKBANK.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "TATAMOTORS.NS"
]

MID_CAP_UNIVERSE = [
    "TRENT.NS", "HAL.NS", "TATAELXSI.NS", "IRCTC.NS", "DIXON.NS",
    "POLYCAB.NS", "CUMMINSIND.NS", "COFORGE.NS", "PERSISTENT.NS", "AUBANK.NS",
    "IDFCFIRSTB.NS", "FEDERALBNK.NS", "PAGEIND.NS", "VOLTAS.NS", "MAXHEALTH.NS",
    "OBEROIRLTY.NS", "LUPIN.NS", "BSE.NS", "INDHOTEL.NS", "MRF.NS"
]

SMALL_CAP_UNIVERSE = [
    "SUZLON.NS", "YESBANK.NS", "IDEA.NS", "RPOWER.NS", "JPPOWER.NS",
    "SOUTHBANK.NS", "GMRINFRA.NS", "HCC.NS", "URJA.NS", "PCJEWELLER.NS",
    "RVNL.NS", "IRFC.NS", "UCOBANK.NS", "IEX.NS", "NHPC.NS",
    "ZOMATO.NS", "PAYTM.NS", "NYKAA.NS", "EASEMYTRIP.NS", "RCOM.NS"
]

class MarketService:
    @staticmethod
    def get_today_date_str() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def get_daily_picks():
        today = MarketService.get_today_date_str()
        return PicksRepository.get_daily_picks(today)

    @staticmethod
    def score_and_rank_universe(universe_name: str, symbols: list) -> list:
        logger.info(f"Evaluating universe: {universe_name}...")
        results = []
        
        def process_symbol(symbol):
            try:
                res = PredictionService.predict_stock(symbol)
                if "error" in res:
                    return None
                    
                predicted_price = res.get("xgb_predicted_price") or res.get("predicted_price", res["current_price"])
                upside_pct = ((predicted_price - res["current_price"]) / res["current_price"]) * 100
                
                if upside_pct <= 0:
                    return None
                
                news_score = res.get("news_sentiment", 0) * 10
                fundamental_score = res.get("fundamental_score", 50) - 50
                rsi = res.get("rsi", 50)
                rsi_bonus = (50 - rsi) * 0.2
                macd = res.get("macd", 0)
                macd_bonus = 5 if macd > 0 else -5
                
                composite_score = (upside_pct * 10) + news_score + fundamental_score + rsi_bonus + macd_bonus
                
                if composite_score != composite_score:
                    composite_score = 0
                    
                return {
                    "symbol": symbol.replace(".NS", ""),
                    "full_symbol": symbol,
                    "current_price": res["current_price"],
                    "target_price": predicted_price,
                    "upside": round(upside_pct, 2),
                    "score": round(composite_score, 1),
                    "confidence": res.get("day_close_confidence", "Moderate"),
                    "sentiment": res.get("news_impact", "neutral").capitalize(),
                    "reasoning": f"AI model projects {round(upside_pct, 2)}% upside. Technical trend is {res.get('trend', 'neutral')}."
                }
            except Exception as e:
                logger.error(f"Error evaluating {symbol}: {e}")
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future_to_symbol = {executor.submit(process_symbol, sym): sym for sym in symbols}
            for future in concurrent.futures.as_completed(future_to_symbol):
                res = future.result()
                if res:
                    results.append(res)
                
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:10]

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
                logger.warning(f"Another worker process is already generating picks for {today}. Skipping duplicate execution.")
                return
                
        picks = MarketService.get_daily_picks()
        if picks is not None and not force:
            if isinstance(picks, list):
                logger.info(f"Found legacy array format for {today}. Forcing regeneration to multi-cap format.")
            else:
                has_anomaly = False
                if isinstance(picks, dict):
                    large_caps = set(LARGE_CAP_UNIVERSE)
                    mid_caps = set(MID_CAP_UNIVERSE)
                    for cap, cap_picks in picks.items():
                        for pick in cap_picks:
                            symbol = pick.get("symbol", "").upper() + ".NS"
                            upside = pick.get("upside", 0)
                            if symbol in large_caps and upside > 3.0:
                                has_anomaly = True
                                break
                            elif symbol in mid_caps and upside > 5.0:
                                has_anomaly = True
                                break
                            elif symbol not in large_caps and symbol not in mid_caps and upside > 8.0:
                                has_anomaly = True
                                break
                
                if not has_anomaly:
                    logger.info(f"Already generated valid multi-cap picks for {today}. Skipping.")
                    return
                else:
                    logger.info(f"Detected abnormal predictions for {today}. Forcing auto-regeneration.")
            
        logger.info(f"Starting comprehensive daily AI screening for {today}...")
        large_cap_picks = MarketService.score_and_rank_universe("Large Cap", LARGE_CAP_UNIVERSE)
        mid_cap_picks = MarketService.score_and_rank_universe("Mid Cap", MID_CAP_UNIVERSE)
        small_cap_picks = MarketService.score_and_rank_universe("Small Cap / Penny", SMALL_CAP_UNIVERSE)
        
        final_picks = {
            "large_cap": large_cap_picks,
            "mid_cap": mid_cap_picks,
            "small_cap": small_cap_picks
        }
        
        picks_json_str = json.dumps(final_picks)
        PicksRepository.save_daily_picks(today, picks_json_str)
        logger.info(f"Successfully saved multi-cap picks for {today}.")
