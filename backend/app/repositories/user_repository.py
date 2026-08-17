from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger
from datetime import datetime
import json
import os

logger = get_logger("user_repository")

_BACKUP_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data_cache", "users_backup.json")

def _load_user_backup() -> list[dict]:
    if os.path.exists(_BACKUP_FILE):
        try:
            with open(_BACKUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    return []

def _save_user_backup(users: list[dict]):
    try:
        os.makedirs(os.path.dirname(_BACKUP_FILE), exist_ok=True)
        with open(_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save user backup: {e}")

class UserRepository:
    @staticmethod
    def init_users_db():
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        if is_postgres:
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    email         VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    name          VARCHAR(255) NOT NULL,
                    age           INTEGER NOT NULL,
                    created_at    VARCHAR(255) NOT NULL,
                    profile_photo TEXT,
                    role          VARCHAR(50) DEFAULT 'user'
                )
            """)
            c.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo TEXT")
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'user'")
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    email       TEXT    UNIQUE NOT NULL,
                    password_hash TEXT  NOT NULL,
                    name        TEXT    NOT NULL,
                    age         INTEGER NOT NULL,
                    created_at  TEXT    NOT NULL,
                    profile_photo TEXT,
                    role        TEXT DEFAULT 'user'
                )
            """)
        conn.commit()
        
        # Add profile_photo and role columns safely for SQLite or older DBs
        for col_name, col_type in [("profile_photo", "TEXT"), ("role", "VARCHAR(50) DEFAULT 'user'")]:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                conn.commit()
            except Exception:
                conn.rollback()

        # Check if users table is empty and restore from persistent backup
        try:
            c.execute("SELECT COUNT(*) as cnt FROM users" if is_postgres else "SELECT COUNT(*) FROM users")
            row = c.fetchone()
            count = (row["cnt"] if is_postgres else row[0]) if row else 0
            if count == 0:
                backup = _load_user_backup()
                if backup:
                    logger.info(f"Restoring {len(backup)} registered users from persistent backup...")
                    for u in backup:
                        try:
                            if is_postgres:
                                c.execute("""
                                    INSERT INTO users (email, password_hash, name, age, created_at, profile_photo, role)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (email) DO NOTHING
                                """, (u["email"].lower().strip(), u["password_hash"], u["name"], u.get("age", 25), u.get("created_at", ""), u.get("profile_photo"), u.get("role", "user")))
                            else:
                                c.execute("""
                                    INSERT INTO users (email, password_hash, name, age, created_at, profile_photo, role)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    ON CONFLICT(email) DO NOTHING
                                """, (u["email"].lower().strip(), u["password_hash"], u["name"], u.get("age", 25), u.get("created_at", ""), u.get("profile_photo"), u.get("role", "user")))
                        except Exception as re:
                            logger.error(f"Error restoring user {u.get('email')}: {re}")
                    conn.commit()
        except Exception as e:
            logger.error(f"Error checking user count for restoration: {e}")

        conn.close()

    @staticmethod
    def get_user_by_email(email: str) -> dict | None:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        try:
            execute_query(c, "SELECT id, email, name, age, password_hash, created_at, profile_photo, role FROM users WHERE email = ?", (email.lower().strip(),), is_postgres)
            row = c.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.warning(f"Full SELECT failed in get_user_by_email for '{email}', attempting fallback: {e}")
            try:
                execute_query(c, "SELECT id, email, name, age, password_hash, created_at FROM users WHERE email = ?", (email.lower().strip(),), is_postgres)
                row = c.fetchone()
                conn.close()
                if row:
                    res = dict(row)
                    res["profile_photo"] = res.get("profile_photo", None)
                    res["role"] = res.get("role", "user")
                    return res
                return None
            except Exception as e2:
                logger.error(f"Fallback get_user_by_email failed: {e2}")
                conn.close()
                raise e

    @staticmethod
    def get_user_by_id(user_id: int) -> dict | None:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        try:
            execute_query(c, "SELECT id, email, name, age, created_at, profile_photo, role FROM users WHERE id = ?", (user_id,), is_postgres)
            row = c.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception:
            execute_query(c, "SELECT id, email, name, age, created_at FROM users WHERE id = ?", (user_id,), is_postgres)
            row = c.fetchone()
            conn.close()
            if row:
                res = dict(row)
                res["profile_photo"] = res.get("profile_photo", None)
                res["role"] = res.get("role", "user")
                return res
            return None

    @staticmethod
    def create_user(email: str, password_hash: str, name: str, age: int, role: str = "user") -> dict | None:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sql = """INSERT INTO users (email, password_hash, name, age, created_at, role)
                 VALUES (?, ?, ?, ?, ?, ?)"""
        try:
            if is_postgres:
                sql = sql.replace("?", "%s") + " RETURNING id"
                c.execute(sql, (email.lower().strip(), password_hash, name.strip(), age, now, role))
                user_id = c.fetchone()["id"]
            else:
                execute_query(c, sql, (email.lower().strip(), password_hash, name.strip(), age, now, role), False)
                user_id = c.lastrowid
            conn.commit()
            conn.close()

            user_dict = {"id": user_id, "email": email.lower().strip(), "password_hash": password_hash, "name": name.strip(), "age": age, "created_at": now, "profile_photo": None, "role": role}
            
            # Sync to persistent backup file
            backup = _load_user_backup()
            backup = [u for u in backup if u.get("email", "").lower() != email.lower().strip()]
            backup.append(user_dict)
            _save_user_backup(backup)

            return user_dict
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            conn.close()
            return None

    @staticmethod
    def update_profile_fields(user_id: int, fields: dict) -> bool:
        if not fields:
            return False
        ALLOWED_COLUMNS = {"name", "profile_photo", "role"}
        for k in fields.keys():
            if k not in ALLOWED_COLUMNS:
                raise ValueError(f"Unauthorized column update: {k}")

        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        
        set_clauses = []
        params = []
        for k, v in fields.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        
        params.append(user_id)
        sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
        
        try:
            execute_query(c, sql, tuple(params), is_postgres)
            conn.commit()
            updated = c.rowcount > 0
            conn.close()

            if updated:
                backup = _load_user_backup()
                for u in backup:
                    if str(u.get("id")) == str(user_id):
                        for k, v in fields.items():
                            u[k] = v
                _save_user_backup(backup)

            return updated
        except Exception as e:
            logger.error(f"Error updating profile fields: {e}")
            conn.close()
            return False

    @staticmethod
    def update_password(user_id: int, new_password_hash: str) -> bool:
        conn, is_postgres = get_db_connection()
        c = conn.cursor()
        try:
            execute_query(c, "UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, user_id), is_postgres)
            conn.commit()
            updated = c.rowcount > 0
            conn.close()

            if updated:
                backup = _load_user_backup()
                for u in backup:
                    if str(u.get("id")) == str(user_id):
                        u["password_hash"] = new_password_hash
                _save_user_backup(backup)

            return updated
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            conn.close()
            return False
