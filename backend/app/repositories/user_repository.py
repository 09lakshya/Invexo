from app.core.database import get_db_connection, get_cursor, execute_query
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger("user_repository")

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
        
        # Add profile_photo and role columns safely if not exist
        for col_name, col_type in [("profile_photo", "TEXT"), ("role", "VARCHAR(50) DEFAULT 'user'")]:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                conn.commit()
            except Exception:
                pass
        conn.close()

    @staticmethod
    def get_user_by_email(email: str) -> dict | None:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(c, "SELECT id, email, name, age, password_hash, created_at, profile_photo, role FROM users WHERE email = ?", (email.lower().strip(),), is_postgres)
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_user_by_id(user_id: int) -> dict | None:
        conn, is_postgres = get_db_connection()
        c = get_cursor(conn, is_postgres)
        execute_query(c, "SELECT id, email, name, age, created_at, profile_photo, role FROM users WHERE id = ?", (user_id,), is_postgres)
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

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
                execute_query(c, sql, (email.lower().strip(), password_hash, name.strip(), age, now, role), False)
                user_id = c.fetchone()["id"]
            else:
                execute_query(c, sql, (email.lower().strip(), password_hash, name.strip(), age, now, role), False)
                user_id = c.lastrowid
            conn.commit()
            conn.close()
            return {"id": user_id, "email": email.lower().strip(), "name": name.strip(), "age": age, "profile_photo": None, "role": role}
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
            return updated
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            conn.close()
            return False
