"""
Signal Ledger repository (Phase 1).

Two tables:

  signal_ledger   — APPEND-ONLY. One immutable row per prediction the
                    consensus model emits. No update/delete methods exist
                    here and no write endpoints are exposed; corrections are
                    made by inserting a NEW row with `corrects_signal_id`
                    pointing at the original.

  signal_outcomes — realized outcome of a signal at a given horizon, written
                    exactly ONCE per (signal_id, horizon). Kept separate from
                    the ledger so scoring never mutates an immutable signal.

Timestamps are stored as ISO-8601 UTC strings *with* offset (e.g.
"2026-07-06T09:20:00+00:00") — portable across Postgres and the SQLite
fallback, lexically sortable, and unambiguous about timezone (per project
rule: store UTC with tz info). All symbols are full NSE tickers (e.g.
RELIANCE.NS).
"""

import json
from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger

logger = get_logger("signal_repository")

# Horizons scored for every signal.
HORIZONS = ("1h", "1d", "3d")

# Confidence buckets (consensus confidence is clamped to [35, 95] upstream).
# Buckets are half-open [low, high) except the last which is inclusive.
CONFIDENCE_BUCKETS = [
    ("35-50", 35, 50),
    ("50-65", 50, 65),
    ("65-80", 65, 80),
    ("80-95", 80, 95.0001),
]


def confidence_bucket(conf) -> str | None:
    """Map a confidence score to its bucket label (pure; unit-tested)."""
    if conf is None:
        return None
    try:
        c = float(conf)
    except (TypeError, ValueError):
        return None
    for label, lo, hi in CONFIDENCE_BUCKETS:
        if lo <= c < hi:
            return label
    return None


def _bucket_range(label: str):
    for lbl, lo, hi in CONFIDENCE_BUCKETS:
        if lbl == label:
            return lo, hi
    return None


class SignalRepository:
    # ── Schema ────────────────────────────────────────────────────────
    @staticmethod
    def init_signal_ledger_db():
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            if is_postgres:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS signal_ledger (
                        id                 SERIAL PRIMARY KEY,
                        signal_ts          TEXT NOT NULL,
                        scan_id            VARCHAR(64) NOT NULL,
                        symbol             VARCHAR(50) NOT NULL,
                        direction          VARCHAR(10) NOT NULL,
                        confidence         REAL,
                        regime             VARCHAR(20),
                        indicator_states   TEXT,
                        sentiment_score    REAL,
                        entry_price        REAL NOT NULL,
                        adx                REAL,
                        rsi                REAL,
                        volatility         REAL,
                        model_version      VARCHAR(40) NOT NULL,
                        corrects_signal_id INTEGER,
                        raw_prediction     TEXT
                    )
                """)
                c.execute("ALTER TABLE signal_ledger ENABLE ROW LEVEL SECURITY")
                c.execute("CREATE INDEX IF NOT EXISTS idx_signal_ledger_ts ON signal_ledger (signal_ts)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_signal_ledger_symbol ON signal_ledger (symbol)")
                c.execute("""
                    CREATE TABLE IF NOT EXISTS signal_outcomes (
                        id          SERIAL PRIMARY KEY,
                        signal_id   INTEGER NOT NULL REFERENCES signal_ledger(id),
                        horizon     VARCHAR(4) NOT NULL,
                        scored_ts   TEXT NOT NULL,
                        exit_price  REAL NOT NULL,
                        return_pct  REAL NOT NULL,
                        hit         INTEGER,
                        mae_pct     REAL,
                        UNIQUE(signal_id, horizon)
                    )
                """)
                c.execute("ALTER TABLE signal_outcomes ENABLE ROW LEVEL SECURITY")
            else:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS signal_ledger (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        signal_ts          TEXT NOT NULL,
                        scan_id            TEXT NOT NULL,
                        symbol             TEXT NOT NULL,
                        direction          TEXT NOT NULL,
                        confidence         REAL,
                        regime             TEXT,
                        indicator_states   TEXT,
                        sentiment_score    REAL,
                        entry_price        REAL NOT NULL,
                        adx                REAL,
                        rsi                REAL,
                        volatility         REAL,
                        model_version      TEXT NOT NULL,
                        corrects_signal_id INTEGER,
                        raw_prediction     TEXT
                    )
                """)
                c.execute("CREATE INDEX IF NOT EXISTS idx_signal_ledger_ts ON signal_ledger (signal_ts)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_signal_ledger_symbol ON signal_ledger (symbol)")
                c.execute("""
                    CREATE TABLE IF NOT EXISTS signal_outcomes (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        signal_id   INTEGER NOT NULL REFERENCES signal_ledger(id),
                        horizon     TEXT NOT NULL,
                        scored_ts   TEXT NOT NULL,
                        exit_price  REAL NOT NULL,
                        return_pct  REAL NOT NULL,
                        hit         INTEGER,
                        mae_pct     REAL,
                        UNIQUE(signal_id, horizon)
                    )
                """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize signal ledger schema: {e}")
            conn.close()
            raise

    # ── Append (the only write to the ledger) ─────────────────────────
    @staticmethod
    def insert_signal(sig: dict) -> int | None:
        """Append one immutable signal row. Returns the new signal id."""
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            cols = (
                "signal_ts", "scan_id", "symbol", "direction", "confidence",
                "regime", "indicator_states", "sentiment_score", "entry_price",
                "adx", "rsi", "volatility", "model_version",
                "corrects_signal_id", "raw_prediction",
            )
            vals = (
                sig["signal_ts"], sig["scan_id"], sig["symbol"], sig["direction"],
                sig.get("confidence"), sig.get("regime"),
                json.dumps(sig.get("indicator_states")) if sig.get("indicator_states") is not None else None,
                sig.get("sentiment_score"), sig["entry_price"], sig.get("adx"),
                sig.get("rsi"), sig.get("volatility"), sig["model_version"],
                sig.get("corrects_signal_id"),
                json.dumps(sig.get("raw_prediction")) if sig.get("raw_prediction") is not None else None,
            )
            placeholders = ", ".join(["?"] * len(cols))
            sql = f"INSERT INTO signal_ledger ({', '.join(cols)}) VALUES ({placeholders})"
            if is_postgres:
                sql += " RETURNING id"
                execute_query(c, sql, vals, is_postgres)
                new_id = c.fetchone()[0]
            else:
                execute_query(c, sql, vals, is_postgres)
                new_id = c.lastrowid
            conn.commit()
            conn.close()
            return new_id
        except Exception as e:
            logger.error(f"Error inserting signal for {sig.get('symbol')}: {e}")
            conn.close()
            return None

    # ── Outcome (write-once) ──────────────────────────────────────────
    @staticmethod
    def record_outcome(signal_id: int, horizon: str, scored_ts: str,
                       exit_price: float, return_pct: float,
                       hit: int | None, mae_pct: float | None) -> bool:
        """Record a realized outcome. Idempotent — a (signal_id, horizon)
        pair is written at most once (ON CONFLICT DO NOTHING)."""
        if horizon not in HORIZONS:
            return False
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            if is_postgres:
                execute_query(c, """
                    INSERT INTO signal_outcomes
                        (signal_id, horizon, scored_ts, exit_price, return_pct, hit, mae_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (signal_id, horizon) DO NOTHING
                """, (signal_id, horizon, scored_ts, exit_price, return_pct, hit, mae_pct), True)
            else:
                execute_query(c, """
                    INSERT OR IGNORE INTO signal_outcomes
                        (signal_id, horizon, scored_ts, exit_price, return_pct, hit, mae_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (signal_id, horizon, scored_ts, exit_price, return_pct, hit, mae_pct), False)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error recording outcome for signal {signal_id}/{horizon}: {e}")
            conn.close()
            return False

    # ── Reads ─────────────────────────────────────────────────────────
    @staticmethod
    def get_signals_pending_scoring(within_days: int = 10) -> list[dict]:
        """Signals from the last `within_days` that still miss ≥1 horizon.

        Returns one dict per signal: its scoring-relevant fields plus the
        set of horizons already scored, so the service can decide what's due.
        """
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=within_days)).date().isoformat()
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        try:
            execute_query(c, """
                SELECT s.id AS signal_id, s.signal_ts, s.symbol, s.direction,
                       s.entry_price, o.horizon AS scored_horizon
                FROM signal_ledger s
                LEFT JOIN signal_outcomes o ON o.signal_id = s.id
                WHERE SUBSTR(s.signal_ts, 1, 10) >= ?
                ORDER BY s.id
            """, (cutoff,), is_postgres)
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching pending scoring signals: {e}")
            conn.close()
            return []

        by_id: dict[int, dict] = {}
        for r in rows:
            sid = r["signal_id"]
            if sid not in by_id:
                by_id[sid] = {
                    "signal_id": sid,
                    "signal_ts": r["signal_ts"],
                    "symbol": r["symbol"],
                    "direction": r["direction"],
                    "entry_price": r["entry_price"],
                    "scored_horizons": set(),
                }
            if r["scored_horizon"]:
                by_id[sid]["scored_horizons"].add(r["scored_horizon"])
        # Only those still missing at least one horizon.
        return [s for s in by_id.values() if len(s["scored_horizons"]) < len(HORIZONS)]

    @staticmethod
    def _fetch_joined(ticker=None, start=None, end=None, regime=None,
                      bucket=None, limit=5000) -> list[dict]:
        """One LEFT JOIN fetch that powers listing, stats and export.
        Returns one row per (signal, outcome) — outcome fields are NULL for
        signals not yet scored. Filters applied in SQL where portable."""
        clauses, params = [], []
        if ticker:
            clauses.append("UPPER(s.symbol) LIKE ?")
            params.append(f"%{ticker.upper().replace('.NS', '').replace('.BO', '')}%")
        if start:
            clauses.append("SUBSTR(s.signal_ts, 1, 10) >= ?")
            params.append(start)
        if end:
            clauses.append("SUBSTR(s.signal_ts, 1, 10) <= ?")
            params.append(end)
        if regime:
            clauses.append("s.regime = ?")
            params.append(regime)
        if bucket:
            rng = _bucket_range(bucket)
            if rng:
                clauses.append("s.confidence >= ? AND s.confidence < ?")
                params.extend([rng[0], rng[1]])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        try:
            execute_query(c, f"""
                SELECT s.id AS signal_id, s.signal_ts, s.scan_id, s.symbol,
                       s.direction, s.confidence, s.regime, s.indicator_states,
                       s.sentiment_score, s.entry_price, s.adx, s.rsi,
                       s.volatility, s.model_version, s.corrects_signal_id,
                       o.horizon, o.exit_price, o.return_pct, o.hit,
                       o.mae_pct, o.scored_ts
                FROM signal_ledger s
                LEFT JOIN signal_outcomes o ON o.signal_id = s.id
                {where}
                ORDER BY s.signal_ts DESC, s.id DESC, o.horizon
                LIMIT ?
            """, (*params, limit), is_postgres)
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Error fetching joined signals: {e}")
            conn.close()
            return []

    @staticmethod
    def get_scan_coverage(day: str) -> list[dict]:
        """Per-scan symbol counts for one day (proves gap-free coverage)."""
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        try:
            execute_query(c, """
                SELECT scan_id, MIN(signal_ts) AS scan_ts, COUNT(*) AS n
                FROM signal_ledger
                WHERE SUBSTR(signal_ts, 1, 10) = ?
                GROUP BY scan_id
                ORDER BY scan_ts
            """, (day,), is_postgres)
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Error fetching scan coverage: {e}")
            conn.close()
            return []
