import bcrypt
import jwt
import os
from datetime import datetime, timedelta, timezone
from app.core.config import JWT_SECRET, JWT_ALGORITHM, JWT_ACCESS_EXPIRY_MINUTES, JWT_REFRESH_EXPIRY_DAYS
from app.core.redis import redis_client
from app.utils.logger import get_logger

logger = get_logger("security")

# bcrypt work factor for NEW/rehashed passwords. Lower = faster login on
# throttled CPUs (e.g. free Render), less brute-force headroom. Configurable
# via env; 10 is the widely accepted minimum. Existing hashes keep their own
# embedded cost until rehashed on next login (see needs_rehash / AuthService).
try:
    BCRYPT_ROUNDS = int(os.environ.get("BCRYPT_ROUNDS", "10"))
except ValueError:
    BCRYPT_ROUNDS = 10
BCRYPT_ROUNDS = max(4, min(15, BCRYPT_ROUNDS))  # clamp to sane bounds

def hash_password(password: str) -> str:
    """Hashes a plain text password using bcrypt at the configured work factor."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.error(f"Error checking password: {e}")
        return False

def needs_rehash(hashed_password: str) -> bool:
    """True if the stored hash's embedded cost differs from BCRYPT_ROUNDS, so
    it should be re-hashed (used for transparent rehash-on-login upgrades)."""
    try:
        cost = int(hashed_password.split("$")[2])
        return cost != BCRYPT_ROUNDS
    except Exception:
        return False

def create_access_token(user_id: int) -> str:
    """Creates a short-lived access token."""
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

import uuid

def create_refresh_token(user_id: int) -> str:
    """Creates a long-lived refresh token and stores it in Redis."""
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_EXPIRY_DAYS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    # Store refresh token in Redis (active list of tokens for user)
    redis_key = f"refresh_token:{user_id}:{token}"
    ttl_seconds = JWT_REFRESH_EXPIRY_DAYS * 86400
    redis_client.setex(redis_key, ttl_seconds, "active")
    
    return token

def verify_access_token(token: str) -> int | None:
    """Verifies access token and returns user ID."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        return None

def verify_refresh_token(token: str) -> int | None:
    """Verifies refresh token and checks if active in Redis (falling back to JWT signature validation if Redis is disabled)."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        sub = payload.get("sub")
        user_id = int(sub) if sub is not None else None
        
        if user_id is None:
            return None
            
        redis_key = f"refresh_token:{user_id}:{token}"
        status = redis_client.get(redis_key)
        
        # If the token has been explicitly marked as revoked, we MUST reject it
        if status == "revoked":
            return None
            
        # If Redis is enabled, we strictly enforce "active" status (missing/expired/revoked means not active)
        if redis_client.enabled:
            if status != "active":
                return None
        else:
            # If Redis is disabled (falling back to memory):
            # We reject if status is set and not "active", but if status is None (not found),
            # we allow it because the memory fallback cache might have been cleared on server restart.
            pass
            
        return user_id
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        return None

def revoke_refresh_token(user_id: int, token: str):
    """Revokes a refresh token in Redis/in-memory cache wrapper by marking it as revoked."""
    redis_key = f"refresh_token:{user_id}:{token}"
    ttl_seconds = JWT_REFRESH_EXPIRY_DAYS * 86400
    redis_client.setex(redis_key, ttl_seconds, "revoked")

def revoke_all_user_tokens(user_id: int):
    """Revokes all refresh tokens for a user by wildcard search."""
    if redis_client.enabled and redis_client.client:
        try:
            pattern = f"refresh_token:{user_id}:*"
            keys = redis_client.client.keys(pattern)
            if keys:
                redis_client.client.delete(*keys)
        except Exception as e:
            logger.error(f"Error revoking all user tokens: {e}")
