from app.core.redis import redis_client
if redis_client.enabled and redis_client.client:
    redis_client.client.flushall()
    print("Redis cache flushed successfully.")
else:
    print("Redis not enabled.")
