import sqlite3
import json
from services.db import get_db_connection, get_cursor

# Setup fake DB
conn, is_postgres = get_db_connection()
c = conn.cursor()
c.execute("DROP TABLE IF EXISTS daily_picks")
c.execute("CREATE TABLE daily_picks (date TEXT, picks_json TEXT)")
fake_data = {"large_cap": [{"symbol": "HDFCBANK", "upside": 10.24, "target_price": 800}]}
c.execute("INSERT INTO daily_picks VALUES (?, ?)", ("2026-06-09", json.dumps(fake_data)))
conn.commit()

from main import patch_hdfc_picks
patch_hdfc_picks()

c = conn.cursor()
c.execute("SELECT picks_json FROM daily_picks")
print(c.fetchone()[0])
conn.close()
