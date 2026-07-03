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
            c.execute("""
                CREATE TABLE IF NOT EXISTS pick_outcomes (
                    id           SERIAL PRIMARY KEY,
                    pick_date    TEXT NOT NULL,
                    symbol       VARCHAR(50) NOT NULL,
                    cap          VARCHAR(20) NOT NULL,
                    entry_price  REAL NOT NULL,
                    prob_1d      REAL,
                    prob_5d      REAL,
                    expected_5d  REAL,
                    ret_1d       REAL,
                    ret_5d       REAL,
                    hit_1d       INTEGER,
                    hit_5d       INTEGER,
                    UNIQUE(pick_date, symbol)
                )
            """)
            c.execute("ALTER TABLE pick_outcomes ENABLE ROW LEVEL SECURITY")
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS daily_picks (
                    date TEXT PRIMARY KEY,
                    picks_json TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS pick_outcomes (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    pick_date    TEXT NOT NULL,
                    symbol       TEXT NOT NULL,
                    cap          TEXT NOT NULL,
                    entry_price  REAL NOT NULL,
                    prob_1d      REAL,
                    prob_5d      REAL,
                    expected_5d  REAL,
                    ret_1d       REAL,
                    ret_5d       REAL,
                    hit_1d       INTEGER,
                    hit_5d       INTEGER,
                    UNIQUE(pick_date, symbol)
                )
            """)
        conn.commit()
        conn.close()

    # ── Pick outcome tracking (measures real accuracy) ──────────────

    @staticmethod
    def record_pick_outcomes(pick_date: str, picks: list[dict]):
        """Insert one row per pick so its outcome can be evaluated later."""
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            for p in picks:
                execute_query(c, """
                    INSERT INTO pick_outcomes
                        (pick_date, symbol, cap, entry_price, prob_1d, prob_5d, expected_5d)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (pick_date, symbol) DO NOTHING
                """, (
                    pick_date, p["full_symbol"], p.get("cap", "small_cap"),
                    p["current_price"], p.get("prob_1d"), p.get("prob_5d"),
                    p.get("expected_5d_pct"),
                ), is_postgres)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error recording pick outcomes: {e}")
            conn.close()

    @staticmethod
    def get_pending_outcomes() -> list[dict]:
        """Picks that still need a 1d or 5d outcome filled in."""
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(c, """
            SELECT id, pick_date, symbol, cap, entry_price, ret_1d, ret_5d
            FROM pick_outcomes
            WHERE ret_1d IS NULL OR ret_5d IS NULL
        """, (), is_postgres)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def fill_outcome(outcome_id: int, horizon: str, ret: float):
        """Store the realized return for one pick/horizon."""
        if horizon not in ("1d", "5d"):
            return
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(c, f"""
                UPDATE pick_outcomes
                SET ret_{horizon} = ?, hit_{horizon} = ?
                WHERE id = ?
            """, (ret, 1 if ret > 0 else 0, outcome_id), is_postgres)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error filling outcome {outcome_id}: {e}")
            conn.close()

    @staticmethod
    def get_accuracy_stats(days: int = 90) -> dict:
        """Aggregate realized hit rates and returns over the last N days."""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(c, """
            SELECT
                COUNT(ret_1d) AS n_1d,
                AVG(CAST(hit_1d AS REAL)) AS hit_rate_1d,
                AVG(ret_1d) AS avg_ret_1d,
                COUNT(ret_5d) AS n_5d,
                AVG(CAST(hit_5d AS REAL)) AS hit_rate_5d,
                AVG(ret_5d) AS avg_ret_5d,
                MAX(ret_5d) AS best_ret_5d
            FROM pick_outcomes
            WHERE pick_date >= ?
        """, (cutoff,), is_postgres)
        row = c.fetchone()
        conn.close()
        if not row:
            return {}
        d = dict(row)
        return {
            "window_days": days,
            "evaluated_1d": int(d.get("n_1d") or 0),
            "hit_rate_1d": round(float(d["hit_rate_1d"]) * 100, 1) if d.get("hit_rate_1d") is not None else None,
            "avg_ret_1d_pct": round(float(d["avg_ret_1d"]) * 100, 2) if d.get("avg_ret_1d") is not None else None,
            "evaluated_5d": int(d.get("n_5d") or 0),
            "hit_rate_5d": round(float(d["hit_rate_5d"]) * 100, 1) if d.get("hit_rate_5d") is not None else None,
            "avg_ret_5d_pct": round(float(d["avg_ret_5d"]) * 100, 2) if d.get("avg_ret_5d") is not None else None,
            "best_ret_5d_pct": round(float(d["best_ret_5d"]) * 100, 2) if d.get("best_ret_5d") is not None else None,
        }

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
