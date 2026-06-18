from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger("alert_repository")

class AlertRepository:
    @staticmethod
    def init_alert_db():
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        if is_postgres:
            c.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id           SERIAL PRIMARY KEY,
                    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    symbol       VARCHAR(255) NOT NULL,
                    target_price REAL NOT NULL,
                    condition    VARCHAR(50) NOT NULL, -- 'above' or 'below'
                    is_active    INTEGER DEFAULT 1,    -- 1 = active, 0 = triggered/cancelled
                    created_at   VARCHAR(255) NOT NULL,
                    triggered_at VARCHAR(255)
                )
            """)
            c.execute("ALTER TABLE alerts ENABLE ROW LEVEL SECURITY")
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL,
                    symbol       TEXT NOT NULL,
                    target_price REAL NOT NULL,
                    condition    TEXT NOT NULL, -- 'above' or 'below'
                    is_active    INTEGER DEFAULT 1,
                    created_at   TEXT NOT NULL,
                    triggered_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
        conn.commit()
        conn.close()

    @staticmethod
    def create_alert(user_id: int, symbol: str, target_price: float, condition: str) -> int | None:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """INSERT INTO alerts (user_id, symbol, target_price, condition, is_active, created_at)
                 VALUES (?, ?, ?, ?, 1, ?)"""
        try:
            if is_postgres:
                sql = sql.replace("?", "%s") + " RETURNING id"
                execute_query(c, sql, (user_id, symbol.upper().strip(), target_price, condition.lower().strip(), now), False)
                new_id = c.fetchone()["id"]
            else:
                execute_query(c, sql, (user_id, symbol.upper().strip(), target_price, condition.lower().strip(), now), False)
                new_id = c.lastrowid
            conn.commit()
            conn.close()
            return new_id
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            conn.close()
            return None

    @staticmethod
    def get_user_alerts(user_id: int) -> list[dict]:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            "SELECT id, user_id, symbol, target_price, condition, is_active, created_at, triggered_at FROM alerts WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
            is_postgres
        )
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def delete_alert(user_id: int, alert_id: int) -> bool:
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(
                c,
                "DELETE FROM alerts WHERE id = ? AND user_id = ?",
                (alert_id, user_id),
                is_postgres
            )
            conn.commit()
            deleted = c.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"Error deleting alert: {e}")
            conn.close()
            return False

    @staticmethod
    def get_active_alerts() -> list[dict]:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            "SELECT id, user_id, symbol, target_price, condition, is_active, created_at FROM alerts WHERE is_active = 1",
            (),
            is_postgres
        )
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def trigger_alert(alert_id: int) -> bool:
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            execute_query(
                c,
                "UPDATE alerts SET is_active = 0, triggered_at = ? WHERE id = ?",
                (now, alert_id),
                is_postgres
            )
            conn.commit()
            updated = c.rowcount > 0
            conn.close()
            return updated
        except Exception as e:
            logger.error(f"Error triggering alert {alert_id}: {e}")
            conn.close()
            return False
