from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger

logger = get_logger("picks_repository")

class PicksRepository:
    @staticmethod
    def init_daily_picks_db():
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        if is_postgres:
            c.execute("""
                CREATE TABLE IF NOT EXISTS daily_picks (
                    date TEXT PRIMARY KEY,
                    picks_json TEXT NOT NULL
                )
            """)
            c.execute("ALTER TABLE daily_picks ENABLE ROW LEVEL SECURITY")
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS daily_picks (
                    date TEXT PRIMARY KEY,
                    picks_json TEXT NOT NULL
                )
            """)
        conn.commit()
        conn.close()

    @staticmethod
    def get_daily_picks(today: str) -> dict | list | None:
        import json
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        try:
            execute_query(c, "SELECT picks_json FROM daily_picks WHERE date = ?", (today,), is_postgres)
            row = c.fetchone()
            conn.close()
            if row:
                if is_postgres:
                    return json.loads(row["picks_json"])
                else:
                    return json.loads(row[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching daily picks: {e}")
            conn.close()
            return None

    @staticmethod
    def save_daily_picks(today: str, picks_json_str: str):
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            if is_postgres:
                execute_query(c, """
                    INSERT INTO daily_picks (date, picks_json)
                    VALUES (%s, %s)
                    ON CONFLICT (date) DO UPDATE SET picks_json = EXCLUDED.picks_json
                """, (today, picks_json_str), True)
            else:
                execute_query(c, """
                    INSERT INTO daily_picks (date, picks_json)
                    VALUES (?, ?)
                    ON CONFLICT(date) DO UPDATE SET picks_json=excluded.picks_json
                """, (today, picks_json_str), False)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error saving daily picks: {e}")
            conn.close()
            return False
