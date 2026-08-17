from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger
from datetime import datetime
import json
import os

logger = get_logger("portfolio_repository")

_PORTFOLIO_BACKUP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data_cache", "portfolio_backup.json")

def _load_portfolio_backup() -> list[dict]:
    if os.path.exists(_PORTFOLIO_BACKUP):
        try:
            with open(_PORTFOLIO_BACKUP, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    return []

def _save_portfolio_backup(items: list[dict]):
    try:
        os.makedirs(os.path.dirname(_PORTFOLIO_BACKUP), exist_ok=True)
        with open(_PORTFOLIO_BACKUP, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save portfolio backup: {e}")

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

        # Check if table is empty and restore from persistent backup
        try:
            c.execute("SELECT COUNT(*) as cnt FROM portfolio" if is_postgres else "SELECT COUNT(*) FROM portfolio")
            row = c.fetchone()
            count = (row["cnt"] if is_postgres else row[0]) if row else 0
            if count == 0:
                backup = _load_portfolio_backup()
                if backup:
                    logger.info(f"Restoring {len(backup)} portfolio holdings from persistent backup...")
                    for h in backup:
                        try:
                            sql = """INSERT INTO portfolio (user_id, symbol, company_name, quantity, buy_price, added_on)
                                     VALUES (?, ?, ?, ?, ?, ?)"""
                            if is_postgres:
                                sql = sql.replace("?", "%s")
                            c.execute(sql, (str(h["user_id"]), h["symbol"], h.get("company_name", ""), h["quantity"], h["buy_price"], h.get("added_on", "")))
                        except Exception as re:
                            logger.error(f"Error restoring holding: {re}")
                    conn.commit()
        except Exception as e:
            logger.error(f"Error restoring portfolio backup: {e}")

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
        added_on = datetime.now().strftime("%Y-%m-%d")
        
        sql = """INSERT INTO portfolio
                 (user_id, symbol, company_name, quantity, buy_price, added_on)
                 VALUES (?, ?, ?, ?, ?, ?)"""
        try:
            if is_postgres:
                sql = sql.replace("?", "%s") + " RETURNING id"
                execute_query(
                    c, sql,
                    (str(user_id), symbol.upper().strip(), company_name, quantity,
                     buy_price, added_on),
                    False
                )
                new_id = c.fetchone()["id"]
            else:
                execute_query(
                    c, sql,
                    (str(user_id), symbol.upper().strip(), company_name, quantity,
                     buy_price, added_on),
                    False
                )
                new_id = c.lastrowid
            conn.commit()
            conn.close()

            # Sync to backup
            backup = _load_portfolio_backup()
            backup.append({"id": new_id, "user_id": str(user_id), "symbol": symbol.upper().strip(), "company_name": company_name, "quantity": quantity, "buy_price": buy_price, "added_on": added_on})
            _save_portfolio_backup(backup)

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
            backup = _load_portfolio_backup()
            for h in holdings:
                sym = str(h["symbol"]).upper().strip()
                execute_query(
                    c, sql,
                    (str(user_id), sym,
                     h.get("company_name") or "", h["quantity"], h["buy_price"], added_on),
                    False,
                )
                inserted += 1
                backup.append({"user_id": str(user_id), "symbol": sym, "company_name": h.get("company_name") or "", "quantity": h["quantity"], "buy_price": h["buy_price"], "added_on": added_on})
            conn.commit()
            _save_portfolio_backup(backup)
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

            if deleted:
                backup = _load_portfolio_backup()
                backup = [h for h in backup if not (str(h.get("id")) == str(holding_id) and str(h.get("user_id")) == str(user_id))]
                _save_portfolio_backup(backup)

            return deleted
        except Exception as e:
            logger.error(f"Error removing holding: {e}")
            conn.close()
            return False
