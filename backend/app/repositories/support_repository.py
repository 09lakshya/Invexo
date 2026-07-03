from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger("support_repository")

class SupportRepository:
    @staticmethod
    def init_support_db():
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        if is_postgres:
            c.execute("""
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id           SERIAL PRIMARY KEY,
                    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    name         VARCHAR(120) NOT NULL,
                    email        VARCHAR(255) NOT NULL,
                    category     VARCHAR(50) NOT NULL,
                    subject      VARCHAR(200) NOT NULL,
                    message      TEXT NOT NULL,
                    delivered    INTEGER DEFAULT 0,   -- 1 = emailed to team successfully
                    status       VARCHAR(50) DEFAULT 'open', -- open / resolved
                    created_at   VARCHAR(255) NOT NULL
                )
            """)
            c.execute("ALTER TABLE support_tickets ENABLE ROW LEVEL SECURITY")
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER,
                    name         TEXT NOT NULL,
                    email        TEXT NOT NULL,
                    category     TEXT NOT NULL,
                    subject      TEXT NOT NULL,
                    message      TEXT NOT NULL,
                    delivered    INTEGER DEFAULT 0,
                    status       TEXT DEFAULT 'open',
                    created_at   TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
        conn.commit()
        conn.close()

    @staticmethod
    def create_ticket(name: str, email: str, category: str, subject: str,
                      message: str, user_id: int | None = None,
                      delivered: bool = False) -> int | None:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """INSERT INTO support_tickets
                 (user_id, name, email, category, subject, message, delivered, status, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)"""
        params = (user_id, name, email, category, subject, message, 1 if delivered else 0, now)
        try:
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
            logger.error(f"Error creating support ticket: {e}")
            conn.close()
            return None

    @staticmethod
    def mark_delivered(ticket_id: int, delivered: bool) -> bool:
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(
                c,
                "UPDATE support_tickets SET delivered = ? WHERE id = ?",
                (1 if delivered else 0, ticket_id),
                is_postgres
            )
            conn.commit()
            updated = c.rowcount > 0
            conn.close()
            return updated
        except Exception as e:
            logger.error(f"Error updating ticket {ticket_id} delivery status: {e}")
            conn.close()
            return False

    @staticmethod
    def list_tickets(limit: int = 100, offset: int = 0) -> list[dict]:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(
            c,
            """SELECT id, user_id, name, email, category, subject, message,
                      delivered, status, created_at
               FROM support_tickets
               ORDER BY id DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
            is_postgres
        )
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
