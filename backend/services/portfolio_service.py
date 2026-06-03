import sqlite3
import os
from datetime import datetime

DB_DIR = "/var/data"
if os.path.exists(DB_DIR):
    DB_PATH = os.path.join(DB_DIR, "portfolio.db")
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_db_connection():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        return conn, True
    else:
        conn = sqlite3.connect(DB_PATH)
        return conn, False

def get_cursor(conn, is_postgres):
    if is_postgres:
        import psycopg2.extras
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conn.row_factory = sqlite3.Row
        return conn.cursor()

def execute_query(c, sql, params=(), is_postgres=False):
    if is_postgres:
        sql = sql.replace("?", "%s")
    c.execute(sql, params)
    return c

def init_db():
    conn, is_postgres = get_db_connection()
    c = conn.cursor()
    if is_postgres:
        c.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id            SERIAL PRIMARY KEY,
                user_id       VARCHAR(255) NOT NULL,
                symbol        VARCHAR(255) NOT NULL,
                company_name  VARCHAR(255),
                quantity      REAL NOT NULL,
                buy_price     REAL NOT NULL,
                added_on      VARCHAR(255)
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                symbol      TEXT    NOT NULL,
                company_name TEXT,
                quantity    REAL    NOT NULL,
                buy_price   REAL    NOT NULL,
                added_on    TEXT
            )
        """)
    conn.commit()
    conn.close()

init_db()


def get_portfolio(user_id: str):
    conn, is_postgres = get_db_connection()
    c = get_cursor(conn, is_postgres)
    execute_query(c, "SELECT * FROM portfolio WHERE user_id = ?", (user_id,), is_postgres)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_holding(user_id: str, symbol: str, company_name: str,
                quantity: float, buy_price: float) -> int:
    conn, is_postgres = get_db_connection()
    c = get_cursor(conn, is_postgres)
    
    sql = """INSERT INTO portfolio
             (user_id, symbol, company_name, quantity, buy_price, added_on)
             VALUES (?, ?, ?, ?, ?, ?)"""
             
    if is_postgres:
        sql = sql.replace("?", "%s") + " RETURNING id"
        execute_query(
            c, sql,
            (user_id, symbol.upper(), company_name, quantity,
             buy_price, datetime.now().strftime("%Y-%m-%d")),
            False
        )
        new_id = c.fetchone()["id"]
    else:
        execute_query(
            c, sql,
            (user_id, symbol.upper(), company_name, quantity,
             buy_price, datetime.now().strftime("%Y-%m-%d")),
            False
        )
        new_id = c.lastrowid
        
    conn.commit()
    conn.close()
    return new_id


def remove_holding(holding_id: int, user_id: str) -> bool:
    conn, is_postgres = get_db_connection()
    c = conn.cursor()
    execute_query(
        c,
        "DELETE FROM portfolio WHERE id = ? AND user_id = ?",
        (holding_id, user_id),
        is_postgres
    )
    conn.commit()
    deleted = c.rowcount
    conn.close()
    return deleted > 0