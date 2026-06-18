import redis
import os
import json
import time
from services.logger import get_logger

logger = get_logger("redis_client")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

class RedisClientWrapper:
    def __init__(self):
        self.client = None
        self.enabled = False
        self._in_memory_fallback = {}
        
        try:
            self.client = redis.Redis.from_url(
                REDIS_URL, 
                decode_responses=True, 
                socket_connect_timeout=2.0,
                socket_timeout=2.0
            )
            self.client.ping()
            self.enabled = True
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis at {REDIS_URL} ({e}). Falling back to in-memory storage.")
            self.client = None
            self.enabled = False
            
    def get(self, key: str):
        if self.enabled and self.client:
            try:
                return self.client.get(key)
            except Exception as e:
                logger.error(f"Redis get error for key '{key}': {e}")
                
        # In-memory fallback get
        if key in self._in_memory_fallback:
            val, expiry = self._in_memory_fallback[key]
            if expiry is None or time.time() < expiry:
                return val
            else:
                del self._in_memory_fallback[key]
        return None
        
    def set(self, key: str, value: str, ex=None):
        if self.enabled and self.client:
            try:
                expiration = int(ex) if ex is not None else None
                self.client.set(key, value, ex=expiration)
                return True
            except Exception as e:
                logger.error(f"Redis set error for key '{key}': {e}")
                
        # In-memory fallback set
        expiry = time.time() + ex if ex is not None else None
        self._in_memory_fallback[key] = (value, expiry)
        return True
        
    def setex(self, key: str, time_secs: int, value: str):
        return self.set(key, value, ex=time_secs)
        
    def delete(self, key: str):
        if self.enabled and self.client:
            try:
                self.client.delete(key)
                return True
            except Exception as e:
                logger.error(f"Redis delete error for key '{key}': {e}")
                
        if key in self._in_memory_fallback:
            del self._in_memory_fallback[key]
        return True
        
    def ttl(self, key: str) -> int:
        if self.enabled and self.client:
            try:
                return self.client.ttl(key)
            except Exception as e:
                logger.error(f"Redis ttl error for key '{key}': {e}")
                
        if key in self._in_memory_fallback:
            val, expiry = self._in_memory_fallback[key]
            if expiry is None:
                return -1
            remaining = int(expiry - time.time())
            return remaining if remaining > 0 else -2
        return -2

redis_client = RedisClientWrapper()
