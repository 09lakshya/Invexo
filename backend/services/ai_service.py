import yfinance as yf
import numpy as np
import pandas as pd
import ta
import xgboost as xgb
import os
import gc
import concurrent.futures
from app.services.market.ticker_utils import ttl_cache, _working_ticker, _yf_session
from app.utils.logger import get_logger

# Import the refactored modules
from .sentiment import fetch_news_sentiment
from .fundamentals import get_fundamental_data, calculate_fundamental_score, calculate_technical_quality_score
# Note: To use indicators.py, you would import calculate_rsi, etc.

logger = get_logger("ai_service")

_loaded_models = {}

def load_all_models():
    pass

async def load_all_models_async():
    pass

def _safe_float(value, default=None):
    try:
        if value is None:
            return default
        value = float(value)
        if np.isnan(value) or np.isinf(value):
            return default
        return value
    except Exception:
        return default

@ttl_cache(maxsize=100, ttl=300)
def predict_stock(symbol: str) -> dict:
    try:
        stock = yf.Ticker(_working_ticker(symbol), session=_yf_session)
        df = stock.history(period="6mo")
        
        try:
            last_price = stock.fast_info.get("lastPrice")
            if last_price is not None and not np.isnan(last_price):
                if not df.empty:
                    if pd.isna(df['Close'].iloc[-1]):
                        df = df.dropna(subset=["Close"])
                    if not df.empty:
                        last_date = df.index[-1].date()
                        today = pd.Timestamp.now(tz=df.index.tz).date()
                        if last_date < today:
                            new_idx = pd.Timestamp.now(tz=df.index.tz)
                            df.loc[new_idx] = df.iloc[-1]
                            df.at[new_idx, 'Close'] = float(last_price)
                        else:
                            df.iloc[-1, df.columns.get_loc('Close')] = float(last_price)
        except Exception as e:
            logger.error(f"Error patching last price: {e}")

        df = df.dropna(subset=["Close"])
        if df.empty or len(df) < 50:
            return {"error": "Not enough data"}

        close = df["Close"]
        volume = df["Volume"]

        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2])
        change = current_price - prev_price
        percent_change = (change / prev_price) * 100

        # Technical Indicators
        rsi = float(ta.momentum.RSIIndicator(close=close, window=14).rsi().iloc[-1])
        macd_obj = ta.trend.MACD(close=close)
        current_macd = float(macd_obj.macd().iloc[-1])
        current_signal = float(macd_obj.macd_signal().iloc[-1])
        current_histogram = float(macd_obj.macd_diff().iloc[-1])
        
        bb_obj = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
        current_upper = float(bb_obj.bollinger_hband().iloc[-1])
        current_middle = float(bb_obj.bollinger_mavg().iloc[-1])
        current_lower = float(bb_obj.bollinger_lband().iloc[-1])
        
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])
        current_ema9 = float(ta.trend.EMAIndicator(close=close, window=9).ema_indicator().iloc[-1])
        current_ema21 = float(ta.trend.EMAIndicator(close=close, window=21).ema_indicator().iloc[-1])
        
        adx_obj = ta.trend.ADXIndicator(high=df["High"], low=df["Low"], close=df["Close"], window=14)
        current_adx = float(adx_obj.adx().iloc[-1])
        current_plus_di = float(adx_obj.adx_pos().iloc[-1])
        current_minus_di = float(adx_obj.adx_neg().iloc[-1])
        
        stoch_obj = ta.momentum.StochasticOscillator(high=df["High"], low=df["Low"], close=df["Close"], window=14, smooth_window=3)
        current_stoch_k = float(stoch_obj.stoch().iloc[-1])
        current_stoch_d = float(stoch_obj.stoch_signal().iloc[-1])
        
        avg_volume = volume.rolling(20).mean().iloc[-1]
        current_volume = volume.iloc[-1]
        volume_signal = current_volume / avg_volume if avg_volume > 0 else 1

        # Fetch sentiment & fundamentals concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_news = executor.submit(fetch_news_sentiment, symbol)
            future_fundamentals = executor.submit(get_fundamental_data, symbol)
            news_data = future_news.result()
            fundamentals = future_fundamentals.result()
            
        news_sentiment = news_data.get("sentiment_score", 50)
        fundamental_score = calculate_fundamental_score(fundamentals)
        fundamental_source = "fundamentals"
        if fundamental_score is None:
            fundamental_score = calculate_technical_quality_score(close, volume)
            fundamental_source = "technical_proxy"

        # Trend Consensus
        signals_direction = {
            "ema_cross": "BULLISH" if current_ema9 > current_ema21 else "BEARISH",
            "macd": "BULLISH" if current_histogram > 0 else "BEARISH",
            "rsi": "BULLISH" if rsi < 35 or (35 <= rsi <= 65 and rsi > 50) else "BEARISH",
            "stochastic": "BULLISH" if current_stoch_k > current_stoch_d else "BEARISH",
            "bollinger": "BULLISH" if current_price > current_middle else "BEARISH",
            "sentiment": "BULLISH" if news_sentiment > 55 else "BEARISH" if news_sentiment < 45 else "NEUTRAL",
            "fundamentals": "BULLISH" if fundamental_score > 55 else "BEARISH" if fundamental_score < 45 else "NEUTRAL"
        }

        trend_score = 0
        if signals_direction["ema_cross"] == "BULLISH": trend_score += 1.5
        else: trend_score -= 1.5
        if signals_direction["macd"] == "BULLISH": trend_score += 1.5
        else: trend_score -= 1.5
        if signals_direction["rsi"] == "BULLISH": trend_score += 1.0
        else: trend_score -= 1.0
        if signals_direction["stochastic"] == "BULLISH": trend_score += 1.0
        else: trend_score -= 1.0
        if signals_direction["bollinger"] == "BULLISH": trend_score += 0.5
        else: trend_score -= 0.5
        if signals_direction["sentiment"] == "BULLISH": trend_score += 0.8
        elif signals_direction["sentiment"] == "BEARISH": trend_score -= 0.8
        if signals_direction["fundamentals"] == "BULLISH": trend_score += 0.7
        elif signals_direction["fundamentals"] == "BEARISH": trend_score -= 0.7

        if current_adx > 25:
            if trend_score > 0 and current_plus_di > current_minus_di: trend_score += 1.0
            elif trend_score < 0 and current_minus_di > current_plus_di: trend_score -= 1.0

        trend = "BULLISH" if trend_score > 0.5 else "BEARISH" if trend_score < -0.5 else "NEUTRAL"
        consensus_ratio = (sum(1 for v in signals_direction.values() if v == ("BULLISH" if trend == "BULLISH" else "BEARISH")) / sum(1 for v in signals_direction.values() if v != "NEUTRAL")) if trend != "NEUTRAL" else 0.5

        # Expected Move Calculation
        volatility = close.pct_change().rolling(20).std().iloc[-1]
        if np.isnan(volatility) or volatility == 0:
            volatility = 0.015
        sentiment_factor = (news_sentiment - 50) / 100
        fundamental_factor = (fundamental_score - 50) / 100
        
        momentum_5d = (close.iloc[-1] / close.iloc[-min(6, len(close))] - 1) / 5
        momentum_20d = (close.iloc[-1] / close.iloc[-min(21, len(close))] - 1) / 20
        mean_reversion = ((current_middle - current_price) / current_price) / 10 if current_price else 0
        
        trend_strength = min(1.0, max(0.0, (current_adx - 15) / 30))
        w_momentum = 0.20 + 0.40 * trend_strength
        w_reversion = 0.35 - 0.25 * trend_strength
        w_sentiment = 0.05
        w_fundamental = 0.05

        expected_move = (
            (momentum_5d * 0.6 + momentum_20d * 0.4) * w_momentum
            + mean_reversion * w_reversion
            + (sentiment_factor / 10) * w_sentiment
            + (fundamental_factor / 10) * w_fundamental
        )
        
        max_move = max(0.015, min(0.04, volatility * 1.5))
        expected_move = max(-max_move, min(max_move, expected_move))
        predicted_price = current_price * (1 + expected_move)

        # Intraday / Day Close
        x = np.arange(len(close))
        y = close.values
        coefficients = np.polyfit(x[-20:], y[-20:], 1)
        slope = coefficients[0]
        intraday_bias = expected_move * 0.35
        day_close_prediction = current_price * (1 + intraday_bias) + slope * 0.35
        day_close_prediction = max(min(day_close_prediction, current_upper), current_lower)

        # Confidence Calibration
        base_confidence = 50 + (consensus_ratio - 0.5) * 80
        adx_boost = min(10.0, (current_adx - 25) * 0.5) if current_adx > 25 else 0.0
        vol_penalty = min(10.0, volatility * 150)
        richness_bonus = (3.0 if news_data.get("source") == "news" else -3.0) + (3.0 if fundamental_source == "fundamentals" else -3.0)
        
        confidence = int(max(35, min(95, round(base_confidence + adx_boost - vol_penalty + richness_bonus))))
        agreement_boost = 4.0 if (1 if slope > 0 else -1) == (1 if expected_move > 0 else -1) else -4.0
        day_close_confidence = int(max(40, min(97, round(base_confidence + (adx_boost * 0.6) - (vol_penalty * 1.2) + agreement_boost))))

        final_predicted = round(predicted_price, 2)
        
        # Local Feature Impact/Explanation
        feature_impacts = {
            "Trend Momentum": float(round(expected_move * 10, 4)),
            "News Sentiment": float(round(sentiment_factor * 0.5, 4)),
            "Fundamentals": float(round(fundamental_factor * 0.3, 4)),
            "RSI": float(round((50 - rsi) * 0.01, 4)),
            "MACD": float(round(current_histogram * 0.1, 4))
        }
        
        result = {
            "current_price": round(current_price, 2),
            "change": round(change, 2),
            "percent_change": round(percent_change, 2),
            "predicted_price": round(predicted_price, 2),
            "day_close_prediction": round(day_close_prediction, 2),
            "confidence": confidence,
            "day_close_confidence": day_close_confidence,
            "trend": trend,
            "rsi": round(float(rsi), 2),
            "macd": round(current_histogram, 4),
            "volatility": round(volatility * 100, 2),
            "news_sentiment": float(round(news_sentiment, 2)),
            "news_impact": news_data.get("impact", "neutral"),
            "news_count": news_data.get("news_count", 0),
            "sentiment_source": news_data.get("source", "news"),
            "fundamental_score": float(round(fundamental_score, 2)),
            "fundamental_source": fundamental_source,
            "fundamental_data_points": fundamentals.get("data_points", 0),
            "pe_ratio": fundamentals.get("pe_ratio"),
            "earnings_growth": fundamentals.get("earnings_growth"),
            "revenue_growth": fundamentals.get("revenue_growth"),
            "prediction": final_predicted,
            "explanation": {
                "summary": f"The model predicts a {trend} movement with a confidence of {confidence}%. Primary driver: {max(feature_impacts, key=lambda k: abs(feature_impacts[k]))}.",
                "shap_values": feature_impacts
            }
        }

        del df, close, volume, stock
        gc.collect()
        return result
    except Exception as e:
        logger.error(f"Prediction Error for {symbol}: {e}")
        return {"error": "Prediction failed"}
