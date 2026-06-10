import os
import json
import time
import concurrent.futures
from datetime import datetime
from services.db import get_db_connection, get_cursor, execute_query
from services.ai_service import predict_stock

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
        c.execute("ALTER TABLE daily_picks ENABLE ROW LEVEL SECURITY")
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

def score_and_rank_universe(universe_name, symbols):
    """Evaluates a list of symbols and returns the top 5 to 10 sorted by AI score."""
    print(f"[Daily Picks] Evaluating universe: {universe_name}...")
    results = []
    
    def process_symbol(symbol):
        try:
            res = predict_stock(symbol)
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
            print(f"[Daily Picks] Error evaluating {symbol}: {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_to_symbol = {executor.submit(process_symbol, sym): sym for sym in symbols}
        for future in concurrent.futures.as_completed(future_to_symbol):
            res = future.result()
            if res:
                results.append(res)
            
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]  # Return top 10

def generate_daily_picks(force=False):
    """Runs the AI model on all universes, picks top stocks, and saves them."""
    today = get_today_date_str()
    
    # Atomic file-based lock to prevent multiple uvicorn worker processes from running concurrently
    import tempfile
    lock_file = os.path.join(tempfile.gettempdir(), f"invexo_picks_{today}.lock")
    if not force:
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, b"locked")
            os.close(fd)
        except FileExistsError:
            print(f"[Daily Picks] Another worker process is already generating picks for {today}. Skipping duplicate execution.")
            return
            
    picks = get_daily_picks()
    if picks is not None and not force:
        if isinstance(picks, list):
            print(f"[Daily Picks] Found legacy array format for {today}. Forcing regeneration to multi-cap format.")
        else:
            # Check for legacy abnormal predictions (e.g. >3% for large caps, >5% for mid caps, >8% for small caps)
            # and auto-trigger regeneration if found.
            has_anomaly = False
            if isinstance(picks, dict):
                large_caps = {
                    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
                    "ITC", "SBIN", "BHARTIARTL", "HINDUNILVR", "BAJFINANCE",
                    "LT", "KOTAKBANK", "AXISBANK", "ASIANPAINT", "MARUTI",
                    "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO", "TATAMOTORS"
                }
                mid_caps = {
                    "TRENT", "HAL", "TATAELXSI", "IRCTC", "DIXON",
                    "POLYCAB", "CUMMINSIND", "COFORGE", "PERSISTENT", "AUBANK",
                    "IDFCFIRSTB", "FEDERALBNK", "PAGEIND", "VOLTAS", "MAXHEALTH",
                    "OBEROIRLTY", "LUPIN", "BSE", "INDHOTEL", "MRF"
                }
                for cap, cap_picks in picks.items():
                    for pick in cap_picks:
                        symbol = pick.get("symbol", "").upper().replace(".NS", "").replace(".BO", "")
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
                print(f"[Daily Picks] Already generated valid multi-cap picks for {today}. Skipping.")
                return
            else:
                print(f"[Daily Picks] Detected abnormal predictions for {today}. Forcing auto-regeneration.")
        
    print(f"[Daily Picks] Starting comprehensive daily AI screening for {today}...")
    
    large_cap_picks = score_and_rank_universe("Large Cap", LARGE_CAP_UNIVERSE)
    mid_cap_picks = score_and_rank_universe("Mid Cap", MID_CAP_UNIVERSE)
    small_cap_picks = score_and_rank_universe("Small Cap / Penny", SMALL_CAP_UNIVERSE)
    
    final_picks = {
        "large_cap": large_cap_picks,
        "mid_cap": mid_cap_picks,
        "small_cap": small_cap_picks
    }
    
    conn, is_postgres = get_db_connection()
    c = conn.cursor()
    
    picks_json_str = json.dumps(final_picks)
    
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
    
    print(f"[Daily Picks] Successfully saved multi-cap picks for {today}.")
