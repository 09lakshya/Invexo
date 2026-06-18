import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from app.services.market.ticker_utils import ttl_cache, _working_ticker, _yf_session
from app.services.ai.feature_engineering import news_text
from app.utils.logger import get_logger

logger = get_logger("sentiment_service")

class SentimentService:
    @staticmethod
    def analyze_financial_sentiment(text: str) -> float:
        if not text:
            return 50.0
            
        hf_token = os.environ.get("HF_API_KEY")
        short_text = str(text)[:500]
        
        if hf_token:
            try:
                API_URL = "https://api-inference.huggingface.co/models/ProsusAI/finbert"
                headers = {"Authorization": f"Bearer {hf_token}"}
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
                    logger.error(f"HF API Error {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"HF API Exception: {e}")
                
        # Fallback to TextBlob
        try:
            from textblob import TextBlob
            blob = TextBlob(short_text)
            polarity = blob.sentiment.polarity
            return ((polarity + 1.0) / 2.0) * 100.0
        except Exception as e:
            logger.error(f"TextBlob error: {e}")
            return 50.0

    @staticmethod
    def _market_sentiment_proxy(symbol: str):
        try:
            stock = yf.Ticker(_working_ticker(symbol))
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

    @staticmethod
    @ttl_cache(maxsize=100, ttl=1800)
    def fetch_news_sentiment(symbol: str):
        try:
            stock = yf.Ticker(_working_ticker(symbol), session=_yf_session)
            try:
                news = stock.news
                if not news:
                    return SentimentService._market_sentiment_proxy(symbol)
                
                sentiments = []
                weights = []
                for idx, item in enumerate(news[:10]):
                    text = news_text(item)
                    if text:
                        sentiment = SentimentService.analyze_financial_sentiment(text)
                        sentiments.append(sentiment)
                        weights.append(10 - idx)

                if not sentiments:
                    return SentimentService._market_sentiment_proxy(symbol)
                
                avg_sentiment = float(np.average(sentiments, weights=weights)) if sentiments else 50.0
                
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
            except Exception:
                return SentimentService._market_sentiment_proxy(symbol)
        except Exception as e:
            logger.error(f"News sentiment error: {e}")
            return SentimentService._market_sentiment_proxy(symbol)
