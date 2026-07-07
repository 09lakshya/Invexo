import yfinance as yf
import numpy as np
import pandas as pd
import ta
import xgboost as xgb
import os
import gc
import concurrent.futures
from app.services.market.ticker_utils import ttl_cache, _working_ticker, _yf_session
from app.services.ai.model_loader import get_model
from app.services.ai.sentiment_service import SentimentService
from app.services.ai.feature_engineering import safe_float
from app.utils.logger import get_logger

logger = get_logger("prediction_service")

# Version marker for the consensus predictor. Bump whenever the signal
# logic (indicator set, weighting, confidence calibration) changes so the
# Signal Ledger can attribute each logged prediction to a specific model.
MODEL_VERSION = "consensus_v1.0"

class PredictionService:
    @staticmethod
    @ttl_cache(maxsize=100, ttl=86400)
    def get_fundamental_data(symbol: str) -> dict:
        try:
            stock = yf.Ticker(_working_ticker(symbol), session=_yf_session)
            info = stock.get_info() or {}
            fast_info = getattr(stock, "fast_info", {}) or {}
            
            fundamentals = {
                "pe_ratio": safe_float(info.get("trailingPE")),
                "pb_ratio": safe_float(info.get("priceToBook")),
                "dividend_yield": safe_float(info.get("dividendYield"), 0),
                "earnings_growth": safe_float(info.get("earningsGrowth"), 0),
                "revenue_growth": safe_float(info.get("revenueGrowth"), 0),
                "profit_margin": safe_float(info.get("profitMargins"), 0),
                "debt_to_equity": safe_float(info.get("debtToEquity")),
                "roa": safe_float(info.get("returnOnAssets"), 0),
                "roe": safe_float(info.get("returnOnEquity"), 0),
                "market_cap": safe_float(info.get("marketCap") or fast_info.get("market_cap"), 0),
                "data_points": 0,
            }

            fundamentals["data_points"] = sum(
                1 for key in [
                    "pe_ratio", "pb_ratio", "dividend_yield", "earnings_growth",
                    "revenue_growth", "profit_margin", "debt_to_equity", "roa",
                    "roe", "market_cap"
                ]
                if fundamentals.get(key) not in (None, 0)
            )
            return fundamentals
        except Exception as e:
            logger.error(f"Fundamental data error: {e}")
            return {}

    @staticmethod
    def calculate_fundamental_score(fundamentals: dict) -> float | None:
        score = 50
        factors = 0
        
        try:
            pe = fundamentals.get("pe_ratio")
            if pe and pe > 0:
                if pe < 15:
                    score += 10
                elif pe > 30:
                    score -= 5
                factors += 1
            
            eg = fundamentals.get("earnings_growth", 0)
            if eg and eg > 0:
                score += min(eg * 10, 15)
                factors += 1
            elif eg and eg < 0:
                score -= min(abs(eg) * 10, 10)
                factors += 1
            
            rg = fundamentals.get("revenue_growth", 0)
            if rg and rg > 0:
                score += min(rg * 5, 10)
                factors += 1
            
            roe = fundamentals.get("roe", 0)
            if roe and roe > 0.15:
                score += 8
                factors += 1
            elif roe and roe < 0:
                score -= 8
                factors += 1
            
            dte = fundamentals.get("debt_to_equity")
            if dte and dte > 2:
                score -= 5
                factors += 1
            elif dte and dte < 1:
                score += 5
                factors += 1
            
            dy = fundamentals.get("dividend_yield", 0)
            if dy and dy > 0.02:
                score += 5
                factors += 1
        except Exception as e:
            logger.error(f"Fundamental scoring error: {e}")
        
        if factors == 0:
            return None

        reliability = min(1, factors / 4)
        score = 50 + ((score - 50) * reliability)
        return max(0, min(100, score))

    @staticmethod
    def calculate_technical_quality_score(close: pd.Series, volume: pd.Series) -> float:
        returns = close.pct_change().dropna()
        if returns.empty:
            return 50

        momentum_3m = close.iloc[-1] / close.iloc[-min(63, len(close))] - 1
        momentum_1m = close.iloc[-1] / close.iloc[-min(22, len(close))] - 1
        volatility = returns.tail(60).std() * np.sqrt(252)
        drawdown = close.iloc[-1] / close.tail(min(126, len(close))).max() - 1
        avg_volume = volume.tail(min(20, len(volume))).mean()

        score = 50
        score += max(-18, min(18, momentum_3m * 80))
        score += max(-10, min(10, momentum_1m * 70))
        score -= max(0, min(12, (volatility - 0.25) * 25))
        score += max(-8, min(4, drawdown * 20))
        if avg_volume and avg_volume > 0:
            score += 3

        return max(20, min(80, score))

    @staticmethod
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
                future_news = executor.submit(SentimentService.fetch_news_sentiment, symbol)
                future_fundamentals = executor.submit(PredictionService.get_fundamental_data, symbol)
                news_data = future_news.result()
                fundamentals = future_fundamentals.result()
                
            news_sentiment = news_data.get("sentiment_score", 50)
            fundamental_score = PredictionService.calculate_fundamental_score(fundamentals)
            fundamental_source = "fundamentals"
            if fundamental_score is None:
                fundamental_score = PredictionService.calculate_technical_quality_score(close, volume)
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

            # XGBoost Predictor Model
            xgb_prediction = None
            model = get_model(symbol)
            if model is not None:
                try:
                    roc_5 = float(ta.momentum.ROCIndicator(close=close, window=5).roc().iloc[-1])
                    roc_20 = float(ta.momentum.ROCIndicator(close=close, window=20).roc().iloc[-1])
                    vol_ema_20 = float(ta.trend.EMAIndicator(close=volume, window=20).ema_indicator().iloc[-1])
                    
                    features = [
                        current_price, current_volume, rsi, current_macd, current_signal, current_histogram,
                        current_upper, current_middle, current_lower, current_upper - current_lower,
                        current_ema9, current_ema21, current_adx, current_plus_di, current_minus_di,
                        current_stoch_k, current_stoch_d, roc_5, roc_20, vol_ema_20
                    ]
                    X_pred = pd.DataFrame([features], columns=[
                        'Close', 'Volume', 'rsi', 'macd', 'macd_signal', 'macd_diff',
                        'bb_upper', 'bb_middle', 'bb_lower', 'bb_width',
                        'ema9', 'ema21', 'adx', 'plus_di', 'minus_di',
                        'stoch_k', 'stoch_d', 'roc_5', 'roc_20', 'vol_ema_20'
                    ])
                    raw_xgb = float(model.predict(X_pred)[0])
                    xgb_prediction = current_price * (1 + raw_xgb) if abs(raw_xgb) < 2.0 else raw_xgb
                    
                    xgb_change_pct = (xgb_prediction - current_price) / current_price
                    if abs(xgb_change_pct) > 0.15:
                        logger.warning(f"XGBoost prediction for {symbol} is unrealistic ({xgb_prediction:.2f}). Discarding.")
                        xgb_prediction = None
                    else:
                        # Cap safety checks based on cap
                        symbol_clean = symbol.upper()
                        suffix_symbol = symbol_clean if (symbol_clean.endswith(".NS") or symbol_clean.endswith(".BO")) else f"{symbol_clean}.NS"
                        large_caps = {"RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS"}
                        mid_caps = {"TRENT.NS", "HAL.NS", "TATAELXSI.NS", "IRCTC.NS"}
                        max_xgb_change = 0.03 if suffix_symbol in large_caps else 0.05 if suffix_symbol in mid_caps else 0.08
                        if abs(xgb_change_pct) > max_xgb_change:
                            xgb_prediction = current_price * (1 + np.clip(xgb_change_pct, -max_xgb_change, max_xgb_change))
                except Exception as ex:
                    logger.error(f"XGB inference error for {symbol}: {ex}")

            final_predicted = round(xgb_prediction or predicted_price, 2)
            
            # Local Feature Impact/Explanation (Simulated SHAP values)
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
                "xgb_predicted_price": round(xgb_prediction, 2) if xgb_prediction else None,
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
                # Enterprise Specs: Confidence, Explanations, Prediction
                "prediction": final_predicted,
                # ── Signal Ledger fields (see signal_ledger_service) ──────
                # Explicit market-regime label derived from the same ADX
                # threshold the consensus weighting already uses (ADX > 25
                # = a directional/trending tape, else range-bound). Emitted
                # so every logged signal records the regime it was made in.
                "regime": "trending" if current_adx > 25 else "range_bound",
                "adx": round(float(current_adx), 2),
                # Per-indicator directional votes at signal time.
                "indicator_states": signals_direction,
                "model_version": MODEL_VERSION,
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
