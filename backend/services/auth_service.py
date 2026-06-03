import sqlite3
import os
import bcrypt
import jwt
import warnings
import random
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# Global in-memory OTP store. Format: { email: { "otp": str, "expires": datetime, "payload": dict } }
otp_store = {}

def send_otp_email(email_addr: str, otp: str):
    """Prints OTP to console. If SMTP variables or RESEND_API_KEY are present, sends it."""
    # Build clean console banner
    print("\n" + "="*50)
    print(f"[OTP DEBUG] OTP for {email_addr}: {otp}")
    print("="*50 + "\n")

    # 1. Try Resend HTTP API if configured (Bypasses SMTP port blocks)
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if resend_key:
        try:
            import requests
            sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")
            res = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}"},
                json={
                    "from": sender,
                    "to": [email_addr],
                    "subject": "Invexo - Verify Your Email",
                    "text": (
                        f"Thank you for signing up for Invexo!\n\n"
                        f"Your 6-digit verification code (OTP) is: {otp}\n\n"
                        f"This code will expire in 5 minutes. Please do not share it with anyone."
                    )
                },
                timeout=10
            )
            if res.status_code in [200, 201]:
                print(f"[Resend] Successfully sent OTP email to {email_addr}")
                return
            else:
                raise RuntimeError(f"Resend API error (status {res.status_code}): {res.text}")
        except Exception as e:
            print(f"[Resend ERROR] Failed to send email to {email_addr}: {e}")
            raise RuntimeError(f"Email delivery failed via Resend API: {str(e)}")

    # 2. Try SMTP credentials if configured
    host = os.environ.get("SMTP_HOST", "")
    port_str = os.environ.get("SMTP_PORT", "")
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("SMTP_FROM", user)

    if host and port_str and user and password:
        try:
            port = int(port_str)
            msg = MIMEText(
                f"Thank you for signing up for Invexo!\n\n"
                f"Your 6-digit verification code (OTP) is: {otp}\n\n"
                f"This code will expire in 5 minutes. Please do not share it with anyone."
            )
            msg["Subject"] = "Invexo - Verify Your Email"
            msg["From"] = sender
            msg["To"] = email_addr

            # Connect and send
            import smtplib
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                server.starttls()
            server.login(user, password)
            server.sendmail(sender, [email_addr], msg.as_string())
            server.quit()
            print(f"[SMTP] Successfully sent OTP email to {email_addr}")
        except Exception as e:
            print(f"[SMTP ERROR] Failed to send email to {email_addr}: {e}")
            raise RuntimeError(f"Email delivery failed: {str(e)}")


def initiate_signup_otp(email_addr: str, payload: dict) -> str:
    """Generates 6-digit OTP, stores signup payload, and triggers send."""
    otp = f"{random.randint(100000, 999999)}"
    expiry = datetime.now() + timedelta(minutes=5)
    otp_store[email_addr.lower()] = {
        "otp": otp,
        "expires": expiry,
        "payload": payload
    }
    send_otp_email(email_addr, otp)
    return otp


def verify_signup_otp(email_addr: str, otp: str) -> dict | None:
    """Verifies OTP. Returns stored user payload on success, None on invalid/expired."""
    key = email_addr.lower()
    if key not in otp_store:
        return None
    
    record = otp_store[key]
    if datetime.now() > record["expires"]:
        del otp_store[key]
        return None
        
    if record["otp"] != otp:
        return None
        
    payload = record["payload"]
    del otp_store[key]
    return payload

DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30  # Long-lived tokens for "keep me signed in"

if not JWT_SECRET:
    JWT_SECRET = "dev_only_change_me"
    warnings.warn(
        "JWT_SECRET is not set. Using insecure development default. "
        "Set JWT_SECRET in production.",
        RuntimeWarning,
    )


def init_users_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    UNIQUE NOT NULL,
            password_hash TEXT  NOT NULL,
            name        TEXT    NOT NULL,
            age         INTEGER NOT NULL,
            created_at  TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_users_db()


def signup(email: str, password: str, name: str, age: int) -> dict | None:
    """Create a new user. Returns user dict on success, None if email already exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Check if email already exists
    c.execute("SELECT id FROM users WHERE email = ?", (email.lower(),))
    if c.fetchone():
        conn.close()
        return None

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute(
        """INSERT INTO users (email, password_hash, name, age, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (email.lower(), password_hash, name.strip(), age, now),
    )
    conn.commit()
    user_id = c.lastrowid
    conn.close()

    return {"id": user_id, "email": email.lower(), "name": name.strip(), "age": age}


def login(email: str, password: str) -> dict | None:
    """Validate credentials. Returns user dict on success, None on failure."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        return None

    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "age": row["age"],
    }


def get_user(user_id: int) -> dict | None:
    """Fetch a user by ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, email, name, age, created_at FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)


def update_profile(user_id: int, name: str) -> dict | None:
    """Update editable profile fields and return updated user."""
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        return None

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET name = ? WHERE id = ?", (cleaned_name, user_id))
    conn.commit()
    updated = c.rowcount > 0
    conn.close()

    if not updated:
        return None
    return get_user(user_id)


def change_password(user_id: int, current_password: str, new_password: str) -> bool:
    """Change password for a user after verifying the current password."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return False

    if not bcrypt.checkpw(current_password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        conn.close()
        return False

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()
    return True


def create_token(user_id: int) -> str:
    """Create a JWT token for the given user ID."""
    payload = {
        "sub": str(user_id),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> int | None:
    """Verify a JWT token and return the user ID, or None if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        return None
