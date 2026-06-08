import os
import json
import time
from datetime import datetime
from services.db import get_db_connection, get_cursor, execute_query
from services.ai_service import predict_stock

# A high-liquidity universe to screen daily
# These are top components of NIFTY 50 and popular stocks
NIFTY_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "HINDUNILVR.NS", "BAJFINANCE.NS",
    "L&T.NS", "KOTAKBANK.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "TATAMOTORS.NS"
]

def init_daily_picks_db():
    """Ensure the daily_picks table exists."""
    conn, is_postgres = get_db_connection()
    c = conn.cursor()
    if is_postgres:
        c.execute("""
            CREATE TABLE IF NOT EXISTS daily_picks (
                date TEXT PRIMARY KEY,
                picks_json TEXT NOT NULL
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS daily_picks (
                date TEXT PRIMARY KEY,
                picks_json TEXT NOT NULL
            )
        """)
    conn.commit()
    conn.close()

init_daily_picks_db()

def get_today_date_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_daily_picks():
    """Retrieve today's daily picks if they exist."""
    conn, is_postgres = get_db_connection()
    c = get_cursor(conn, is_postgres)
    today = get_today_date_str()
    
    execute_query(c, "SELECT picks_json FROM daily_picks WHERE date = ?", (today,), is_postgres)
    row = c.fetchone()
    conn.close()
    
    if row:
        if is_postgres:
            return json.loads(row["picks_json"])
        else:
            return json.loads(row[0])
    return None

def generate_daily_picks():
    """Runs the AI model on the universe, picks top 3, and saves them."""
    today = get_today_date_str()
    
    # Check if already generated for today
    if get_daily_picks() is not None:
        print(f"[Daily Picks] Already generated for {today}. Skipping.")
        return
        
    print(f"[Daily Picks] Starting daily AI screening for {today}...")
    
    results = []
    
    for symbol in NIFTY_UNIVERSE:
        print(f"[Daily Picks] Evaluating {symbol}...")
        try:
            # Predict stock runs XGBoost, technicals, and news sentiment
            res = predict_stock(symbol)
            if "error" in res:
                continue
                
            # Composite Scoring Logic
            # We want high predicted upside, positive sentiment, and good fundamentals.
            # Upside % from XGBoost
            predicted_price = res.get("xgb_predicted_price") or res.get("predicted_price", res["current_price"])
            upside_pct = ((predicted_price - res["current_price"]) / res["current_price"]) * 100
            
            # Fundamentals & Sentiment
            news_score = res.get("news_sentiment", 0) * 10  # Range approx -10 to +10
            fundamental_score = res.get("fundamental_score", 50) - 50 # Centered around 0
            
            # Technical Bonus: MACD positive is good, RSI oversold (< 40) is good
            rsi = res.get("rsi", 50)
            rsi_bonus = (50 - rsi) * 0.2  # Max ~10 points bonus if oversold
            macd = res.get("macd", 0)
            macd_bonus = 5 if macd > 0 else -5
            
            # Final composite score
            # A 1% upside is roughly 10 points
            composite_score = (upside_pct * 10) + news_score + fundamental_score + rsi_bonus + macd_bonus
            
            # Convert NaN to 0 if any
            if composite_score != composite_score:
                composite_score = 0
                
            results.append({
                "symbol": symbol.replace(".NS", ""), # Clean up for UI
                "full_symbol": symbol,
                "current_price": res["current_price"],
                "target_price": predicted_price,
                "upside": round(upside_pct, 2),
                "score": round(composite_score, 1),
                "confidence": res.get("day_close_confidence", "Moderate"),
                "sentiment": res.get("news_impact", "neutral").capitalize(),
                "reasoning": f"AI model projects {round(upside_pct, 2)}% upside. Technical trend is {res.get('trend', 'neutral')}."
            })
            
            # Sleep briefly to avoid rate limits on news/finance APIs
            time.sleep(1)
            
        except Exception as e:
            print(f"[Daily Picks] Error evaluating {symbol}: {e}")
            continue
            
    # Sort by highest composite score
    results.sort(key=lambda x: x["score"], reverse=True)
    
    # Pick top 3
    top_picks = results[:3]
    
    # Save to database
    conn, is_postgres = get_db_connection()
    c = conn.cursor()
    
    picks_json_str = json.dumps(top_picks)
    
    if is_postgres:
        execute_query(c, """
            INSERT INTO daily_picks (date, picks_json)
            VALUES (%s, %s)
            ON CONFLICT (date) DO UPDATE SET picks_json = EXCLUDED.picks_json
        """, (today, picks_json_str), True)
    else:
        execute_query(c, """
            INSERT INTO daily_picks (date, picks_json)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET picks_json=excluded.picks_json
        """, (today, picks_json_str), False)
        
    conn.commit()
    conn.close()
    
    print(f"[Daily Picks] Successfully saved {len(top_picks)} top picks for {today}.")
