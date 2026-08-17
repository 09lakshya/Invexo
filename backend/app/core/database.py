import sqlite3
import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
import psycopg2.extras
from app.core.config import DATABASE_URL, ENV, RENDER, USE_SQLITE
from app.utils.logger import get_logger

logger = get_logger("database")

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
render_disk = os.environ.get("RENDER_DISK_PATH", base_dir)
_sqlite_db_path = os.path.join(render_disk, "invexo.db")

db_pool = None
use_sqlite_fallback = False
_sqlite_initialized = False

def ensure_sqlite_tables_init():
    global _sqlite_initialized
    if not _sqlite_initialized:
        _sqlite_initialized = True
        try:
            from app.repositories.user_repository import UserRepository
            from app.repositories.picks_repository import PicksRepository
            from app.repositories.portfolio_repository import PortfolioRepository
            from app.repositories.watchlist_repository import WatchlistRepository
            from app.repositories.alert_repository import AlertRepository
            from app.repositories.signal_alert_repository import SignalAlertRepository
            from app.repositories.support_repository import SupportRepository
            from app.repositories.signal_repository import SignalRepository

            logger.info("Initializing SQLite schemas for fallback...")
            UserRepository.init_users_db()
            PicksRepository.init_daily_picks_db()
            PortfolioRepository.init_portfolio_db()
            WatchlistRepository.init_watchlist_db()
            AlertRepository.init_alert_db()
            SignalAlertRepository.init_signal_alert_db()
            SupportRepository.init_support_db()
            SignalRepository.init_signal_ledger_db()
            logger.info("SQLite schemas initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing SQLite fallback schemas: {e}")

def init_db_pool():
    global db_pool, use_sqlite_fallback
    if USE_SQLITE:
        use_sqlite_fallback = True
        ensure_sqlite_tables_init()
        return

    if db_pool is None and not use_sqlite_fallback:
        try:
            logger.info("Initializing PostgreSQL Connection Pool...")
            dsn = DATABASE_URL
            if "connect_timeout" not in dsn:
                dsn += ("&" if "?" in dsn else "?") + "connect_timeout=2"
            db_pool = ThreadedConnectionPool(1, 20, dsn=dsn)
            logger.info("PostgreSQL Connection Pool initialized successfully.")
        except Exception as e:
            logger.warning(f"Failed to connect to PostgreSQL ({e}). Falling back to SQLite ({_sqlite_db_path}).")
            use_sqlite_fallback = True
            ensure_sqlite_tables_init()

class PooledConnectionWrapper:
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._released = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        if not self._released:
            try:
                self._pool.putconn(self._conn)
                self._released = True
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._released = True

    # ── Leak safety net ──────────────────────────────────────────────
    def _safe_return(self):
        if not self._released:
            try:
                self._conn.rollback()
            except Exception:
                pass
            self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            try:
                self._conn.rollback()
            except Exception:
                pass
            self.close()
        return False

    def __del__(self):
        try:
            self._safe_return()
        except Exception:
            pass

def get_db_connection():
    global db_pool, use_sqlite_fallback
    if use_sqlite_fallback:
        ensure_sqlite_tables_init()
        conn = sqlite3.connect(_sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn, False

    if db_pool is None:
        init_db_pool()

    if use_sqlite_fallback:
        ensure_sqlite_tables_init()
        conn = sqlite3.connect(_sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn, False

    try:
        conn = db_pool.getconn()
        wrapped_conn = PooledConnectionWrapper(conn, db_pool)
        return wrapped_conn, True
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed ({e}). Falling back to SQLite.")
        use_sqlite_fallback = True
        ensure_sqlite_tables_init()
        conn = sqlite3.connect(_sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn, False

def get_cursor(conn, is_postgres=True):
    if is_postgres:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()

def execute_query(c, sql, params=(), is_postgres=True):
    if is_postgres:
        sql = sql.replace("?", "%s")
    c.execute(sql, params)
    return c
