import time
from fastapi import Request, HTTPException, status

class InMemoryRateLimiter:
    def __init__(self, requests_limit: int, window_seconds: int):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.requests = {}

    def check_rate_limit(self, ip: str) -> bool:
        now = time.time()
        if ip not in self.requests:
            self.requests[ip] = [now]
            return False

        # Filter out timestamps outside the sliding window
        self.requests[ip] = [t for t in self.requests[ip] if now - t < self.window_seconds]

        if len(self.requests[ip]) >= self.requests_limit:
            return True

        self.requests[ip].append(now)
        return False

# Sensitive endpoints (login, signup, OTP request/verify): max 10 requests per 60 seconds per IP
auth_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60)

async def rate_limit_auth(request: Request):
    # Retrieve client IP, fallback if None
    client_ip = request.client.host if request.client else "unknown"
    if auth_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again in a minute."
        )
