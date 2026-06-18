import os
import warnings
from dotenv import load_dotenv
from app.utils.logger import get_logger

logger = get_logger("config")

load_dotenv()

ENV = os.environ.get("ENV", "development")
RENDER = os.environ.get("RENDER", "false")

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_EXPIRY_MINUTES = 15
JWT_REFRESH_EXPIRY_DAYS = 7

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/invexo")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Security and Fail Startup Check
if not JWT_SECRET:
    if ENV == "production" or RENDER == "true":
        raise ValueError("CRITICAL: JWT_SECRET environment variable is required in production!")
    else:
        JWT_SECRET = "dev_only_insecure_key_change_me_immediately"
        logger.warning(
            "JWT_SECRET is not set. Using insecure development default. "
            "Set JWT_SECRET in production env variables!"
        )
