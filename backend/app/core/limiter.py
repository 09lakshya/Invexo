from slowapi import Limiter
from slowapi.util import get_remote_address
import os

# Rate-limit storage.
#
# Default to fast in-process memory. We deliberately do NOT reuse REDIS_URL:
# on Render that points at a *remote managed* Redis, so a Redis-backed limiter
# adds network round-trips to EVERY rate-limited request (login, signup,
# refresh…) before the handler even runs — a real, avoidable latency tax on a
# free instance. In-memory limiting is per-process; on a single free instance
# with one worker that's exactly right. If you later scale to multiple
# workers/instances and need shared limits, set RATELIMIT_STORAGE_URI to a
# LOW-LATENCY (co-located) Redis.
storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "")
if storage_uri:
    limiter = Limiter(key_func=get_remote_address, storage_uri=storage_uri)
else:
    limiter = Limiter(key_func=get_remote_address)
