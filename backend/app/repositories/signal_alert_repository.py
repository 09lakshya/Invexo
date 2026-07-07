from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger("signal_alert_repository")


def normalize_symbol(symbol: str) -> str:
    """Canonical key for a ticker across subscriptions, watchlist, portfolio and
    notifications. Uppercase and strip the NSE/BSE suffix so 'RELIANCE',
    'reliance' and 'RELIANCE.NS' all collapse to one signal stream."""
    s = (symbol or "").upper().strip()
    for suffix in (".NS", ".BO"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s


class SignalAlertRepository:
    """Buy/Sell signal alerts. Two tables:

      signal_alert_subscriptions — a user's explicit opt-in to receive buy/sell
        signals for a symbol (in addition to the automatic coverage of their
        watchlist and holdings).
      signal_notifications       — the in-app feed: one immutable row per
        emitted buy/sell signal, also used to dedupe (we only notify on a
        *flip* versus the last emitted action for that user+symbol).
    """

    @staticmethod
    def init_signal_alert_db():
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        if is_postgres:
            c.execute("""
                CREATE TABLE IF NOT EXISTS signal_alert_subscriptions (
                    id             SERIAL PRIMARY KEY,
                    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    symbol         VARCHAR(255) NOT NULL,
                    min_confidence INTEGER DEFAULT 60,
                    is_active      INTEGER DEFAULT 1,
                    created_at     VARCHAR(255) NOT NULL,
                    CONSTRAINT unique_signal_sub UNIQUE(user_id, symbol)
                )
            """)
            c.execute("ALTER TABLE signal_alert_subscriptions ENABLE ROW LEVEL SECURITY")
            c.execute("""
                CREATE TABLE IF NOT EXISTS signal_notifications (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    symbol      VARCHAR(255) NOT NULL,
                    action      VARCHAR(10) NOT NULL,   -- 'BUY' or 'SELL'
                    trend       VARCHAR(20),
                    confidence  INTEGER,
                    price       REAL,
                    message     TEXT,
                    source      VARCHAR(20),            -- 'subscription' | 'watchlist' | 'portfolio'
                    is_read     INTEGER DEFAULT 0,
                    created_at  VARCHAR(255) NOT NULL
                )
            """)
            c.execute("ALTER TABLE signal_notifications ENABLE ROW LEVEL SECURITY")
            c.execute("CREATE INDEX IF NOT EXISTS idx_signotif_user ON signal_notifications(user_id, id DESC)")
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS signal_alert_subscriptions (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id        INTEGER NOT NULL,
                    symbol         TEXT NOT NULL,
                    min_confidence INTEGER DEFAULT 60,
                    is_active      INTEGER DEFAULT 1,
                    created_at     TEXT NOT NULL,
                    UNIQUE(user_id, symbol),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS signal_notifications (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    symbol      TEXT NOT NULL,
                    action      TEXT NOT NULL,
                    trend       TEXT,
                    confidence  INTEGER,
                    price       REAL,
                    message     TEXT,
                    source      TEXT,
                    is_read     INTEGER DEFAULT 0,
                    created_at  TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_signotif_user ON signal_notifications(user_id, id DESC)")
        conn.commit()
        conn.close()

    # ── Subscriptions ─────────────────────────────────────────────────────
    @staticmethod
    def create_subscription(user_id: int, symbol: str, min_confidence: int) -> int | None:
        """Create or re-activate a subscription for (user, symbol). Idempotent:
        an existing row is updated in place (avoids DB-specific upsert syntax)."""
        symbol = normalize_symbol(symbol)
        existing = SignalAlertRepository.get_subscription_by_symbol(user_id, symbol)
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if existing:
                execute_query(
                    c,
                    "UPDATE signal_alert_subscriptions SET is_active = 1, min_confidence = ? WHERE id = ?",
                    (min_confidence, existing["id"]),
                    is_postgres,
                )
                conn.commit()
                conn.close()
                return existing["id"]

            sql = """INSERT INTO signal_alert_subscriptions
                     (user_id, symbol, min_confidence, is_active, created_at)
                     VALUES (?, ?, ?, 1, ?)"""
            if is_postgres:
                sql = sql.replace("?", "%s") + " RETURNING id"
                execute_query(c, sql, (user_id, symbol, min_confidence, now), False)
                new_id = c.fetchone()["id"]
            else:
                execute_query(c, sql, (user_id, symbol, min_confidence, now), False)
                new_id = c.lastrowid
            conn.commit()
            conn.close()
            return new_id
        except Exception as e:
            logger.error(f"Error creating signal subscription: {e}")
            conn.close()
            return None

    @staticmethod
    def get_subscription_by_symbol(user_id: int, symbol: str) -> dict | None:
        symbol = normalize_symbol(symbol)
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            "SELECT id, user_id, symbol, min_confidence, is_active, created_at FROM signal_alert_subscriptions WHERE user_id = ? AND symbol = ?",
            (user_id, symbol),
            is_postgres,
        )
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_user_subscriptions(user_id: int) -> list[dict]:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            "SELECT id, user_id, symbol, min_confidence, is_active, created_at FROM signal_alert_subscriptions WHERE user_id = ? AND is_active = 1 ORDER BY id DESC",
            (user_id,),
            is_postgres,
        )
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_active_subscriptions() -> list[dict]:
        """All active subscriptions across every user (for the scan job)."""
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            "SELECT id, user_id, symbol, min_confidence FROM signal_alert_subscriptions WHERE is_active = 1",
            (),
            is_postgres,
        )
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def delete_subscription(user_id: int, subscription_id: int) -> bool:
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(
                c,
                "DELETE FROM signal_alert_subscriptions WHERE id = ? AND user_id = ?",
                (subscription_id, user_id),
                is_postgres,
            )
            conn.commit()
            deleted = c.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"Error deleting signal subscription: {e}")
            conn.close()
            return False

    @staticmethod
    def delete_subscription_by_symbol(user_id: int, symbol: str) -> bool:
        symbol = normalize_symbol(symbol)
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(
                c,
                "DELETE FROM signal_alert_subscriptions WHERE user_id = ? AND symbol = ?",
                (user_id, symbol),
                is_postgres,
            )
            conn.commit()
            deleted = c.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"Error deleting signal subscription by symbol: {e}")
            conn.close()
            return False

    # ── Notifications ─────────────────────────────────────────────────────
    @staticmethod
    def insert_notification(user_id: int, symbol: str, action: str, trend: str,
                            confidence: int, price: float, message: str,
                            source: str) -> int | None:
        symbol = normalize_symbol(symbol)
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """INSERT INTO signal_notifications
                 (user_id, symbol, action, trend, confidence, price, message, source, is_read, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)"""
        try:
            params = (user_id, symbol, action, trend, confidence, price, message, source, now)
            if is_postgres:
                sql = sql.replace("?", "%s") + " RETURNING id"
                execute_query(c, sql, params, False)
                new_id = c.fetchone()["id"]
            else:
                execute_query(c, sql, params, False)
                new_id = c.lastrowid
            conn.commit()
            conn.close()
            return new_id
        except Exception as e:
            logger.error(f"Error inserting signal notification: {e}")
            conn.close()
            return None

    @staticmethod
    def get_last_action(user_id: int, symbol: str) -> str | None:
        """Most recently emitted action ('BUY'/'SELL') for a user+symbol, or
        None if we've never notified them about it. Drives flip detection."""
        symbol = normalize_symbol(symbol)
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            "SELECT action FROM signal_notifications WHERE user_id = ? AND symbol = ? ORDER BY id DESC LIMIT 1",
            (user_id, symbol),
            is_postgres,
        )
        row = c.fetchone()
        conn.close()
        return row["action"] if row else None

    @staticmethod
    def get_user_notifications(user_id: int, limit: int, offset: int) -> list[dict]:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            "SELECT id, user_id, symbol, action, trend, confidence, price, message, source, is_read, created_at "
            "FROM signal_notifications WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
            is_postgres,
        )
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def count_unread(user_id: int) -> int:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            "SELECT COUNT(*) AS n FROM signal_notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
            is_postgres,
        )
        row = c.fetchone()
        conn.close()
        return int(row["n"]) if row else 0

    @staticmethod
    def mark_read(user_id: int, notification_id: int) -> bool:
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(
                c,
                "UPDATE signal_notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
                (notification_id, user_id),
                is_postgres,
            )
            conn.commit()
            updated = c.rowcount > 0
            conn.close()
            return updated
        except Exception as e:
            logger.error(f"Error marking notification read: {e}")
            conn.close()
            return False

    @staticmethod
    def mark_all_read(user_id: int) -> int:
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(
                c,
                "UPDATE signal_notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                (user_id,),
                is_postgres,
            )
            conn.commit()
            n = c.rowcount
            conn.close()
            return n
        except Exception as e:
            logger.error(f"Error marking all notifications read: {e}")
            conn.close()
            return 0
