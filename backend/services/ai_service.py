import yfinance as yf
import numpy as np
import pandas as pd
from textblob import TextBlob
import requests
from bs4 import BeautifulSoup
import os
import time
import gc
from functools import wraps
import json
import xgboost as xgb
import ta

from services.ticker_utils import (
    _yf_session,
    ttl_cache,
    _ticker_candidates,
    _working_ticker as _get_working_ticker,
)

try:
    _yf_cache_dir = os.path.join(os.getenv("TEMP", "C:\\tmp"), "invexo-yfinance-cache")
    os.makedirs(_yf_cache_dir, exist_ok=True)
    yf.set_tz_cache_location(_yf_cache_dir)
except Exception:
    pass

_loaded_models = {}


def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD indicator"""
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(period).mean()
    std = prices.rolling(period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, sma, lower_band


def calculate_adx(df, period=14):
    """Calculate Average Directional Index (ADX)"""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    
    # Calculate True Range (TR)
    h_l = high - low
    h_pc = (high - close.shift(1)).abs()
    # Handle NaN in first rows
    h_pc = h_pc.fillna(0.0)
    l_pc = (low - close.shift(1)).abs()
    l_pc = l_pc.fillna(0.0)
    
    tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    # +DM and -DM calculation
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    plus_dm_series = pd.Series(plus_dm, index=df.index)
    minus_dm_series = pd.Series(minus_dm, index=df.index)
    
    # Wilder's smoothing technique: 1/14 alpha
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    
    # Handle case where ATR is 0 to avoid division by zero
    atr_safe = np.where(atr != 0, atr, 1e-9)
    
    plus_di = 100 * plus_dm_series.ewm(alpha=1/period, adjust=False).mean() / atr_safe
    minus_di = 100 * minus_dm_series.ewm(alpha=1/period, adjust=False).mean() / atr_safe
    
    # Avoid division by zero in DX calculation
    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = 100 * np.where(di_sum != 0, di_diff / di_sum, 0.0)
    
    adx = pd.Series(dx, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    
    return plus_di, minus_di, adx


def calculate_stochastic(df, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator (%K and %D)"""
    low_min = df["Low"].rolling(window=k_period).min()
    high_max = df["High"].rolling(window=k_period).max()
    
    denom = high_max - low_min
    k = 100 * np.where(denom != 0, (df["Close"] - low_min) / denom, 50.0)
    k_series = pd.Series(k, index=df.index)
    d = k_series.rolling(window=d_period).mean()
    
    # Fallback for initial NaN values
    k_series = k_series.fillna(50.0)
    d = d.fillna(50.0)
    return k_series, d


def analyze_financial_sentiment(text):
    """Analyze sentiment using Hugging Face API with TextBlob fallback"""
    if not text:
        return 50.0
        
    hf_token = os.environ.get("HF_API_KEY")
    short_text = str(text)[:500]
    
    if hf_token:
        try:
            API_URL = "https://api-inference.huggingface.co/models/ProsusAI/finbert"
            headers = {"Authorization": f"Bearer {hf_token}"}
            # Add a short timeout so the API doesn't hang the UI
            response = requests.post(API_URL, headers=headers, json={"inputs": short_text}, timeout=3)
            
            if response.status_code == 200:
                result = response.json()[0][0]
                label = result['label']
                score = result['score']
                
                if label == 'positive':
                    return 55.0 + (score * 45.0)
                elif label == 'negative':
                    return 45.0 - (score * 45.0)
                else:
                    return 50.0
            else:
                print(f"HF API Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"HF API Exception: {e}")
            
    # Fallback to TextBlob if HF_API_KEY is missing, rate-limited, or fails
    try:
        blob = TextBlob(short_text)
        polarity = blob.sentiment.polarity
        # Convert -1.0 to 1.0 scale to 0-100 scale
        return ((polarity + 1.0) / 2.0) * 100.0
    except Exception as e:
        print(f"TextBlob error: {e}")
        return 50.0


def analyze_sentiment(text):
    # Keep legacy function signature for safety, routing to upgraded lexicon logic
    return analyze_financial_sentiment(text)


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


def _news_text(item: dict) -> str:
    content = item.get("content") or {}
    title = item.get("title") or content.get("title") or ""
    summary = (
        item.get("summary")
        or item.get("publisher")
        or content.get("summary")
        or content.get("description")
        or ""
    )
    return f"{title} {summary}".strip()


def _market_sentiment_proxy(symbol: str):
    """Fallback when news text is unavailable; keeps neutral from meaning unknown."""
    try:
        stock = yf.Ticker(_get_working_ticker(symbol))
        df = stock.history(period="3mo", interval="1d")
        df = df.dropna(subset=["Close"])
        if df.empty or len(df) < 15:
            return {"sentiment_score": 50, "news_count": 0, "impact": "neutral", "source": "none"}

        close = df["Close"]
        volume = df["Volume"]
        one_month_return = close.iloc[-1] / close.iloc[-min(22, len(close))] - 1
        one_week_return = close.iloc[-1] / close.iloc[-min(6, len(close))] - 1
        volume_ratio = volume.iloc[-5:].mean() / volume.iloc[-20:].mean() if volume.iloc[-20:].mean() > 0 else 1

        score = 50 + (one_month_return * 90) + (one_week_return * 70) + ((volume_ratio - 1) * 8)
        score = max(25, min(75, score))
        impact = "bullish" if score > 58 else "bearish" if score < 42 else "neutral"
        return {
            "sentiment_score": round(score, 2),
            "news_count": 0,
            "impact": impact,
            "source": "market_proxy",
        }
    except Exception:
        return {"sentiment_score": 50, "news_count": 0, "impact": "neutral", "source": "none"}




@ttl_cache(maxsize=100, ttl=1800)
def fetch_news_sentiment(symbol: str):
    """Fetch and analyze news sentiment for a stock"""
    try:
        stock = yf.Ticker(_get_working_ticker(symbol), session=_yf_session)
        
        # Try to get news from yfinance
        try:
            news = stock.news
            if not news:
                return {"sentiment_score": 50, "news_count": 0, "impact": "neutral"}
            
            sentiments = []
            weights = []
            for idx, item in enumerate(news[:10]):  # Last 10 news items
                text = _news_text(item)
                if text:
                    sentiment = analyze_financial_sentiment(text)
                    sentiments.append(sentiment)
                    weights.append(10 - idx)

            if not sentiments:
                return _market_sentiment_proxy(symbol)
            
            avg_sentiment = float(np.average(sentiments, weights=weights)) if sentiments else 50.0
            
            # Determine impact
            if avg_sentiment > 58:
                impact = "bullish"
            elif avg_sentiment < 42:
                impact = "bearish"
            else:
                impact = "neutral"
            
            return {
                "sentiment_score": float(round(avg_sentiment, 2)),
                "news_count": len(sentiments),
                "impact": impact,
                "details": len(sentiments) > 0,
                "source": "news",
            }
        except:
            # Fallback if news not available
            return _market_sentiment_proxy(symbol)
    except Exception as e:
        print(f"News sentiment error: {e}")
        return _market_sentiment_proxy(symbol)


@ttl_cache(maxsize=100, ttl=86400)
def get_fundamental_data(symbol: str):
    """Get fundamental data for a stock"""
    try:
        stock = yf.Ticker(_get_working_ticker(symbol), session=_yf_session)
        info = stock.get_info() or {}
        fast_info = getattr(stock, "fast_info", {}) or {}
        
        fundamentals = {
            "pe_ratio": _safe_float(info.get("trailingPE")),
            "pb_ratio": _safe_float(info.get("priceToBook")),
            "dividend_yield": _safe_float(info.get("dividendYield"), 0),
            "earnings_growth": _safe_float(info.get("earningsGrowth"), 0),
            "revenue_growth": _safe_float(info.get("revenueGrowth"), 0),
            "profit_margin": _safe_float(info.get("profitMargins"), 0),
            "debt_to_equity": _safe_float(info.get("debtToEquity")),
            "roa": _safe_float(info.get("returnOnAssets"), 0),
            "roe": _safe_float(info.get("returnOnEquity"), 0),
            "market_cap": _safe_float(info.get("marketCap") or fast_info.get("market_cap"), 0),
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
        print(f"Fundamental data error: {e}")
        return {}


def calculate_fundamental_score(fundamentals: dict):
    """Calculate a score based on fundamental data"""
    score = 50  # Neutral baseline
    factors = 0
    
    try:
        # PE Ratio analysis
        pe = fundamentals.get("pe_ratio")
        if pe and pe > 0:
            if pe < 15:
                score += 10  # Undervalued
            elif pe > 30:
                score -= 5   # Expensive
            factors += 1
        
        # Earnings growth
        eg = fundamentals.get("earnings_growth", 0)
        if eg and eg > 0:
            score += min(eg * 10, 15)  # Cap at +15
            factors += 1
        elif eg and eg < 0:
            score -= min(abs(eg) * 10, 10)
            factors += 1
        
        # Revenue growth
        rg = fundamentals.get("revenue_growth", 0)
        if rg and rg > 0:
            score += min(rg * 5, 10)
            factors += 1
        
        # ROE (Return on Equity)
        roe = fundamentals.get("roe", 0)
        if roe and roe > 0.15:  # > 15% is good
            score += 8
            factors += 1
        elif roe and roe < 0:
            score -= 8
            factors += 1
        
        # Debt to Equity
        dte = fundamentals.get("debt_to_equity")
        if dte and dte > 2:  # High debt
            score -= 5
            factors += 1
        elif dte and dte < 1:  # Low debt
            score += 5
            factors += 1
        
        # Dividend yield
        dy = fundamentals.get("dividend_yield", 0)
        if dy and dy > 0.02:  # > 2% is good
            score += 5
            factors += 1
        
    except Exception as e:
        print(f"Fundamental scoring error: {e}")
    
    if factors == 0:
        return None

    # Blend back toward neutral when only a few data points are available.
    reliability = min(1, factors / 4)
    score = 50 + ((score - 50) * reliability)
    return max(0, min(100, score))  # Clamp between 0-100


def calculate_technical_quality_score(close, volume):
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


@ttl_cache(maxsize=100, ttl=300)
def predict_stock(symbol: str):
    try:
        # Get more historical data for better accuracy
        stock = yf.Ticker(_get_working_ticker(symbol))
        df = stock.history(period="6mo")  # Reduced from 1y to 6mo to save memory
        
        # Fetch the real-time last price to ensure accuracy and append if necessary
        try:
            last_price = stock.fast_info.get("lastPrice")
            if last_price is not None and not np.isnan(last_price):
                import pandas as pd
                if not df.empty:
                    # If last row's Close is NaN, drop it first
                    if pd.isna(df['Close'].iloc[-1]):
                        df = df.dropna(subset=["Close"])
                    
                    if not df.empty:
                        last_date = df.index[-1].date()
                        today = pd.Timestamp.now(tz=df.index.tz).date()
                        if last_date < today:
                            # Append new row
                            new_idx = pd.Timestamp.now(tz=df.index.tz)
                            df.loc[new_idx] = df.iloc[-1] # copy previous row for defaults
                            df.at[new_idx, 'Close'] = float(last_price)
                        else:
                            # Update today's row
                            df.iloc[-1, df.columns.get_loc('Close')] = float(last_price)
        except Exception as e:
            print("Error patching last price:", e)

        df = df.dropna(subset=["Close"])
        
        if df.empty or len(df) < 50:
            return {"error": "Not enough data"}

        close = df["Close"]
        volume = df["Volume"]

        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2])
        
        change = current_price - prev_price
        percent_change = (change / prev_price) * 100

        # ===== TECHNICAL INDICATORS (using ta library) =====
        rsi = float(ta.momentum.RSIIndicator(close=close, window=14).rsi().iloc[-1])
        
        # MACD
        macd_obj = ta.trend.MACD(close=close)
        current_macd = float(macd_obj.macd().iloc[-1])
        current_signal = float(macd_obj.macd_signal().iloc[-1])
        current_histogram = float(macd_obj.macd_diff().iloc[-1])
        
        # Bollinger Bands
        bb_obj = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
        current_upper = float(bb_obj.bollinger_hband().iloc[-1])
        current_middle = float(bb_obj.bollinger_mavg().iloc[-1])
        current_lower = float(bb_obj.bollinger_lband().iloc[-1])
        
        # Moving Averages (SMA)
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])
        
        # Exponential Moving Averages (EMA 9 and 21)
        current_ema9 = float(ta.trend.EMAIndicator(close=close, window=9).ema_indicator().iloc[-1])
        current_ema21 = float(ta.trend.EMAIndicator(close=close, window=21).ema_indicator().iloc[-1])
        
        # ADX (Average Directional Index)
        adx_obj = ta.trend.ADXIndicator(high=df["High"], low=df["Low"], close=df["Close"], window=14)
        current_adx = float(adx_obj.adx().iloc[-1])
        current_plus_di = float(adx_obj.adx_pos().iloc[-1])
        current_minus_di = float(adx_obj.adx_neg().iloc[-1])
        
        # Stochastic Oscillator
        stoch_obj = ta.momentum.StochasticOscillator(high=df["High"], low=df["Low"], close=df["Close"], window=14, smooth_window=3)
        current_stoch_k = float(stoch_obj.stoch().iloc[-1])
        current_stoch_d = float(stoch_obj.stoch_signal().iloc[-1])
        
        # Volume Analysis
        avg_volume = volume.rolling(20).mean().iloc[-1]
        current_volume = volume.iloc[-1]
        volume_signal = current_volume / avg_volume if avg_volume > 0 else 1

        # ===== SENTIMENT & FUNDAMENTAL ANALYSIS =====
        import concurrent.futures
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

        # ===== SIGNAL CONSENSUS & TREND DETECTION =====
        signals_direction = {}
        
        # 1. EMA 9/21 Trend
        signals_direction["ema_cross"] = "BULLISH" if current_ema9 > current_ema21 else "BEARISH"
        
        # 2. MACD Histogram
        signals_direction["macd"] = "BULLISH" if current_histogram > 0 else "BEARISH"
        
        # 3. RSI
        if rsi < 35:
            signals_direction["rsi"] = "BULLISH"
        elif rsi > 65:
            signals_direction["rsi"] = "BEARISH"
        else:
            signals_direction["rsi"] = "BULLISH" if rsi > 50 else "BEARISH"
            
        # 4. Stochastic Hook
        if current_stoch_k > current_stoch_d:
            signals_direction["stochastic"] = "BULLISH"
        else:
            signals_direction["stochastic"] = "BEARISH"
            
        # 5. Bollinger Bands (Relative position to middle band)
        signals_direction["bollinger"] = "BULLISH" if current_price > current_middle else "BEARISH"
        
        # 6. News Sentiment
        signals_direction["sentiment"] = "BULLISH" if news_sentiment > 55 else "BEARISH" if news_sentiment < 45 else "NEUTRAL"
        
        # 7. Fundamentals
        signals_direction["fundamentals"] = "BULLISH" if fundamental_score > 55 else "BEARISH" if fundamental_score < 45 else "NEUTRAL"

        # Calculate final trend based on consensus score weight
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

        # ADX trend confirmation boost
        if current_adx > 25:
            # Boost the prevailing trend strength if ADX indicates strong trend
            if trend_score > 0 and current_plus_di > current_minus_di:
                trend_score += 1.0
            elif trend_score < 0 and current_minus_di > current_plus_di:
                trend_score -= 1.0

        if trend_score > 0.5:
            trend = "BULLISH"
        elif trend_score < -0.5:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"

        # Calculate signal agreement consensus ratio
        target_dir = "BULLISH" if trend == "BULLISH" else "BEARISH" if trend == "BEARISH" else None
        
        if target_dir:
            matching_signals = sum(1 for k, v in signals_direction.items() if v == target_dir)
            total_valid_signals = sum(1 for k, v in signals_direction.items() if v != "NEUTRAL")
            consensus_ratio = (matching_signals / total_valid_signals) if total_valid_signals > 0 else 0.5
        else:
            # Neutral trend has 50% consensus baseline
            consensus_ratio = 0.5

        # ===== PRICE PREDICTION (ADX Regime Adaptive) =====
        volatility = close.pct_change().rolling(20).std().iloc[-1]
        if np.isnan(volatility) or volatility == 0:
            volatility = 0.015  # Fallback standard deviation

        sentiment_factor = (news_sentiment - 50) / 100  # -0.5 to 0.5
        fundamental_factor = (fundamental_score - 50) / 100  # -0.5 to 0.5
        momentum_5d = close.iloc[-1] / close.iloc[-min(6, len(close))] - 1
        momentum_20d = close.iloc[-1] / close.iloc[-min(21, len(close))] - 1
        mean_reversion = (current_middle - current_price) / current_price if current_price else 0

        # ADX regime scaling: trending vs range-bound
        # Normalize ADX from 0 to 1 between 15 (choppy) and 45 (extremely trending)
        trend_strength = min(1.0, max(0.0, (current_adx - 15) / 30))
        
        # In trending market (high trend_strength), prioritize momentum.
        # In range-bound market (low trend_strength), prioritize mean reversion.
        w_momentum = 0.20 + 0.40 * trend_strength      # ranges [0.20, 0.60]
        w_reversion = 0.35 - 0.25 * trend_strength     # ranges [0.35, 0.10]
        w_sentiment = 0.05
        w_fundamental = 0.05

        expected_move = (
            (momentum_5d * 0.6 + momentum_20d * 0.4) * w_momentum
            + mean_reversion * w_reversion
            + sentiment_factor * w_sentiment
            + fundamental_factor * w_fundamental
        )
        
        max_move = max(0.015, min(0.08, volatility * 2.2))
        expected_move = max(-max_move, min(max_move, expected_move))
        predicted_price = current_price * (1 + expected_move)

        # ===== DAY CLOSE PREDICTION =====
        x = np.arange(len(close))
        y = close.values
        coefficients = np.polyfit(x[-20:], y[-20:], 1)
        slope = coefficients[0]
        
        intraday_bias = expected_move * 0.35
        day_close_prediction = current_price * (1 + intraday_bias) + slope * 0.35
        
        day_close_prediction = max(day_close_prediction, current_lower)
        day_close_prediction = min(day_close_prediction, current_upper)

        # ===== CONFIDENCE CALIBRATION =====
        # Base confidence from consensus ratio (ranges from 50% to 90% typically)
        base_confidence = 50 + (consensus_ratio - 0.5) * 80
        
        # ADX trend strength boost (up to +10 points for strong, clear trends)
        adx_boost = 0.0
        if current_adx > 25:
            adx_boost = min(10.0, (current_adx - 25) * 0.5)
            
        # Volatility penalty (prices are less predictable during high volatility)
        vol_penalty = min(10.0, volatility * 150)
        
        # Data richness adjustments
        richness_bonus = 0.0
        if news_data.get("source") == "news":
            richness_bonus += 3.0
        else:
            richness_bonus -= 3.0
            
        if fundamental_source == "fundamentals":
            richness_bonus += 3.0
        else:
            richness_bonus -= 3.0
            
        raw_confidence = base_confidence + adx_boost - vol_penalty + richness_bonus
        confidence = int(max(35, min(95, round(raw_confidence))))

        # Shorter term (1-day) has slightly higher certainty baseline but is more sensitive to recent trend/slope alignment
        slope_direction = 1 if slope > 0 else -1
        move_direction = 1 if expected_move > 0 else -1
        agreement_boost = 4.0 if slope_direction == move_direction else -4.0
        raw_day_close_conf = base_confidence + (adx_boost * 0.6) - (vol_penalty * 1.2) + agreement_boost
        day_close_confidence = int(max(40, min(97, round(raw_day_close_conf))))

        # ===== XGBOOST INFERENCE =====
        xgb_prediction = None
        try:
            model_base_name = symbol.replace('.NS', '').replace('.BO', '')
            base_dir = os.path.dirname(os.path.dirname(__file__))
            models_dir = os.environ.get("RENDER_DISK_PATH", os.path.join(base_dir, "models"))
            model_path = os.path.join(models_dir, f"{model_base_name}_xgb.json")
            
            if os.path.exists(model_path):
                global _loaded_models
                if model_path not in _loaded_models:
                    model = xgb.XGBRegressor()
                    model.load_model(model_path)
                    _loaded_models[model_path] = model
                else:
                    model = _loaded_models[model_path]
                
                # We need to construct the feature row precisely as it was during training
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
                
                xgb_prediction = float(model.predict(X_pred)[0])
        except Exception as e:
            print(f"XGB inference error for {symbol}: {e}")

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
            # New: News and Sentiment
            "news_sentiment": float(round(news_sentiment, 2)),
            "news_impact": news_data.get("impact", "neutral"),
            "news_count": news_data.get("news_count", 0),
            "sentiment_source": news_data.get("source", "news"),
            # New: Fundamental Analysis
            "fundamental_score": float(round(fundamental_score, 2)),
            "fundamental_source": fundamental_source,
            "fundamental_data_points": fundamentals.get("data_points", 0),
            "pe_ratio": fundamentals.get("pe_ratio"),
            "earnings_growth": fundamentals.get("earnings_growth"),
            "revenue_growth": fundamentals.get("revenue_growth"),
        }

        # Aggressive Garbage Collection to prevent OOM
        del df, close, volume, stock
        gc.collect()
        
        return result

    except Exception as e:
        print("Prediction Error:", e)
        return {"error": "Prediction failed"}
