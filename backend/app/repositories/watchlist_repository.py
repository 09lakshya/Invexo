from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger("watchlist_repository")

class WatchlistRepository:
    @staticmethod
    def init_watchlist_db():
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        if is_postgres:
            c.execute("""
                CREATE TABLE IF NOT EXISTS watchlists (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    symbol      VARCHAR(255) NOT NULL,
                    created_at  VARCHAR(255) NOT NULL,
                    CONSTRAINT unique_user_symbol UNIQUE(user_id, symbol)
                )
            """)
            c.execute("ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY")
        else:
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
        conn.commit()
        conn.close()

    @staticmethod
    def add_to_watchlist(user_id: int, symbol: str) -> bool:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """INSERT INTO watchlists (user_id, symbol, created_at)
                 VALUES (?, ?, ?)"""
        try:
            execute_query(c, sql, (user_id, symbol.upper().strip(), now), is_postgres)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error adding to watchlist: {e}")
            conn.close()
            return False

    @staticmethod
    def remove_from_watchlist(user_id: int, symbol: str) -> bool:
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(
                c,
                "DELETE FROM watchlists WHERE user_id = ? AND symbol = ?",
                (user_id, symbol.upper().strip()),
                is_postgres
            )
            conn.commit()
            deleted = c.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"Error removing from watchlist: {e}")
            conn.close()
            return False

    @staticmethod
    def get_watchlist(user_id: int) -> list[dict]:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(c, "SELECT id, user_id, symbol, created_at FROM watchlists WHERE user_id = ?", (user_id,), is_postgres)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_all_entries() -> list[dict]:
        """Every (user_id, symbol) pair across all users. Used by the signal
        alert scan to auto-cover watched stocks."""
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(c, "SELECT user_id, symbol FROM watchlists", (), is_postgres)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def is_in_watchlist(user_id: int, symbol: str) -> bool:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            "SELECT 1 FROM watchlists WHERE user_id = ? AND symbol = ?",
            (user_id, symbol.upper().strip()),
            is_postgres
        )
        row = c.fetchone()
        conn.close()
        return row is not None
