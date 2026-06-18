import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
import psycopg2.extras
from services.logger import get_logger

logger = get_logger("db")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/invexo")

db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is None:
        try:
            logger.info("Initializing PostgreSQL Connection Pool...")
            db_pool = ThreadedConnectionPool(5, 20, dsn=DATABASE_URL)
            logger.info("PostgreSQL Connection Pool initialized successfully.")
        except Exception as e:
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

def get_db_connection():
    global db_pool
    if db_pool is None:
        init_db_pool()
    try:
        conn = db_pool.getconn()
        wrapped_conn = PooledConnectionWrapper(conn, db_pool)
        return wrapped_conn, True
    except Exception as e:
        logger.error(f"Failed to get database connection from pool: {e}")
        raise

def get_cursor(conn, is_postgres=True):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def execute_query(c, sql, params=(), is_postgres=True):
    sql = sql.replace("?", "%s")
    c.execute(sql, params)
    return c
