import sqlite3
import os

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
