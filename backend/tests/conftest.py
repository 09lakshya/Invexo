import os
import sys
import pytest
import sqlite3

# Ensure app is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_test_db_conn = sqlite3.connect(":memory:", check_same_thread=False)
_test_db_conn.row_factory = sqlite3.Row

class SQLiteConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        pass

wrapped_conn = SQLiteConnectionWrapper(_test_db_conn)

# Initialize schemas on the in-memory SQLite DB
def init_test_schemas():
    c = _test_db_conn.cursor()
    # Create users
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    UNIQUE NOT NULL,
            password_hash TEXT  NOT NULL,
            name        TEXT    NOT NULL,
            age         INTEGER NOT NULL,
            created_at  TEXT    NOT NULL,
            profile_photo TEXT,
            role        TEXT DEFAULT 'user'
        )
    """)
    # Create daily_picks
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_picks (
            date TEXT PRIMARY KEY,
            picks_json TEXT NOT NULL
        )
    """)
    # Create portfolio
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            symbol      TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            UNIQUE(user_id, symbol),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            symbol       TEXT NOT NULL,
            target_price REAL NOT NULL,
            condition    TEXT NOT NULL,
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT NOT NULL,
            triggered_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    _test_db_conn.commit()

init_test_schemas()

# Mock core.database connection functions
import app.core.database as db_module

def mock_get_db_connection():
    # Return SQLite connection, is_postgres = False
    return wrapped_conn, False

db_module.get_db_connection = mock_get_db_connection

# Mock redis to be disabled / use in-memory fallback
from app.core.redis import redis_client
redis_client.enabled = False
redis_client.client = None

# Mock email API calls
from app.services.auth.auth_service import AuthService
AuthService.send_otp_email = lambda email_addr, otp: None
AuthService.send_welcome_email = lambda email_addr, name: None
AuthService.send_password_updated_email = lambda email_addr: None

@pytest.fixture(autouse=True)
def clean_db():
    # Clear tables before each test to guarantee state isolation
    c = _test_db_conn.cursor()
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM daily_picks")
    c.execute("DELETE FROM portfolio")
    c.execute("DELETE FROM watchlists")
    c.execute("DELETE FROM alerts")
    _test_db_conn.commit()
    yield
