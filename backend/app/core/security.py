import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import JWT_SECRET, JWT_ALGORITHM, JWT_ACCESS_EXPIRY_MINUTES, JWT_REFRESH_EXPIRY_DAYS
from app.core.redis import redis_client
from app.utils.logger import get_logger

logger = get_logger("security")

def hash_password(password: str) -> str:
    """Hashes a plain text password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.error(f"Error checking password: {e}")
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
    """Verifies refresh token and checks if active in Redis."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        sub = payload.get("sub")
        user_id = int(sub) if sub is not None else None
        
        if user_id is None:
            return None
            
        # Check if revoked or missing in Redis
        redis_key = f"refresh_token:{user_id}:{token}"
        status = redis_client.get(redis_key)
        if status != "active":
            return None
            
        return user_id
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        return None

def revoke_refresh_token(user_id: int, token: str):
    """Revokes a refresh token in Redis."""
    redis_key = f"refresh_token:{user_id}:{token}"
    redis_client.delete(redis_key)

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
