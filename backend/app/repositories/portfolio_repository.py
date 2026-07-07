from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger("portfolio_repository")

class PortfolioRepository:
    @staticmethod
    def init_portfolio_db():
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
            c.execute("ALTER TABLE portfolio ENABLE ROW LEVEL SECURITY")
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

    @staticmethod
    def get_portfolio(user_id: str) -> list[dict]:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(c, "SELECT id, user_id, symbol, company_name, quantity, buy_price, added_on FROM portfolio WHERE user_id = ?", (str(user_id),), is_postgres)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_all_holdings() -> list[dict]:
        """Distinct (user_id, symbol) across all portfolios. Used by the signal
        alert scan to auto-cover holdings. Note: portfolio user_id is stored as
        text — callers that need an integer must convert."""
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(c, "SELECT DISTINCT user_id, symbol FROM portfolio", (), is_postgres)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def add_holding(user_id: str, symbol: str, company_name: str, quantity: float, buy_price: float) -> int | None:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        
        sql = """INSERT INTO portfolio
                 (user_id, symbol, company_name, quantity, buy_price, added_on)
                 VALUES (?, ?, ?, ?, ?, ?)"""
        try:
            if is_postgres:
                sql = sql.replace("?", "%s") + " RETURNING id"
                execute_query(
                    c, sql,
                    (str(user_id), symbol.upper().strip(), company_name, quantity,
                     buy_price, datetime.now().strftime("%Y-%m-%d")),
                    False
                )
                new_id = c.fetchone()["id"]
            else:
                execute_query(
                    c, sql,
                    (str(user_id), symbol.upper().strip(), company_name, quantity,
                     buy_price, datetime.now().strftime("%Y-%m-%d")),
                    False
                )
                new_id = c.lastrowid
            conn.commit()
            conn.close()
            return new_id
        except Exception as e:
            logger.error(f"Error adding holding: {e}")
            conn.close()
            return None

    @staticmethod
    def bulk_add_holdings(user_id: str, holdings: list[dict]) -> int:
        """Insert many holdings in a single transaction. Returns rows inserted."""
        if not holdings:
            return 0
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        sql = """INSERT INTO portfolio
                 (user_id, symbol, company_name, quantity, buy_price, added_on)
                 VALUES (?, ?, ?, ?, ?, ?)"""
        if is_postgres:
            sql = sql.replace("?", "%s")
        added_on = datetime.now().strftime("%Y-%m-%d")
        inserted = 0
        try:
            for h in holdings:
                execute_query(
                    c, sql,
                    (str(user_id), str(h["symbol"]).upper().strip(),
                     h.get("company_name") or "", h["quantity"], h["buy_price"], added_on),
                    False,
                )
                inserted += 1
            conn.commit()
            return inserted
        except Exception as e:
            conn.rollback()
            logger.error(f"Error bulk-adding holdings: {e}")
            return 0
        finally:
            conn.close()

    @staticmethod
    def remove_holding(holding_id: int, user_id: str) -> bool:
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(
                c,
                "DELETE FROM portfolio WHERE id = ? AND user_id = ?",
                (holding_id, str(user_id)),
                is_postgres
            )
            conn.commit()
            deleted = c.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"Error removing holding: {e}")
            conn.close()
            return False
