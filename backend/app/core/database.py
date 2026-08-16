import sqlite3
import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
import psycopg2.extras
from app.core.config import DATABASE_URL, ENV, RENDER
from app.utils.logger import get_logger

logger = get_logger("database")

db_pool = None
use_sqlite_fallback = False
_sqlite_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "invexo.db")

def init_db_pool():
    global db_pool, use_sqlite_fallback
    if db_pool is None and not use_sqlite_fallback:
        try:
            logger.info("Initializing PostgreSQL Connection Pool...")
            dsn = DATABASE_URL
            if "connect_timeout" not in dsn:
                dsn += ("&" if "?" in dsn else "?") + "connect_timeout=2"
            db_pool = ThreadedConnectionPool(1, 20, dsn=dsn)
            logger.info("PostgreSQL Connection Pool initialized successfully.")
        except Exception as e:
            if ENV != "production" and RENDER != "true":
                logger.warning(f"Failed to connect to PostgreSQL ({e}). Falling back to SQLite ({_sqlite_db_path}) for local development.")
                use_sqlite_fallback = True
            else:
                logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
                raise

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
    # Many repository methods only call close() on their happy path. If a
    # query raises before close(), the raw connection would otherwise never
    # be returned to the pool (max 20) and the pool would eventually exhaust,
    # hanging the whole API. These guards return the connection on every exit
    # path without requiring callers to change. Any pending/aborted
    # transaction is rolled back first so a poisoned connection is never
    # handed to the next caller.
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
        conn = sqlite3.connect(_sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn, False

    if db_pool is None:
        init_db_pool()

    if use_sqlite_fallback:
        conn = sqlite3.connect(_sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn, False

    try:
        conn = db_pool.getconn()
        wrapped_conn = PooledConnectionWrapper(conn, db_pool)
        return wrapped_conn, True
    except Exception as e:
        if ENV != "production" and RENDER != "true":
            logger.warning(f"PostgreSQL connection failed ({e}). Falling back to SQLite.")
            use_sqlite_fallback = True
            conn = sqlite3.connect(_sqlite_db_path)
            conn.row_factory = sqlite3.Row
            return conn, False
        logger.error(f"Failed to get database connection from pool: {e}")
        raise

def get_cursor(conn, is_postgres=True):
    if is_postgres:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()

def execute_query(c, sql, params=(), is_postgres=True):
    if is_postgres:
        sql = sql.replace("?", "%s")
    c.execute(sql, params)
    return c
