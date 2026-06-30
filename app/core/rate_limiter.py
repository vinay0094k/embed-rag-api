"""Rate limiting middleware for API endpoints."""

import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """In-memory rate limiter using token bucket algorithm."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.buckets = defaultdict(lambda: {"tokens": requests_per_minute, "last_update": time.time()})

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for given key (API key or IP)."""
        now = time.time()
        bucket = self.buckets[key]

        # Calculate elapsed time
        elapsed = now - bucket["last_update"]
        bucket["last_update"] = now

        # Add tokens (1 token per second, max requests_per_minute)
        bucket["tokens"] = min(
            self.requests_per_minute,
            bucket["tokens"] + elapsed * (self.requests_per_minute / 60)
        )

        # Check if we have tokens
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True

        return False

    def cleanup_old_buckets(self):
        """Remove buckets older than 1 hour to prevent memory leak."""
        now = time.time()
        old_keys = [
            key for key, bucket in self.buckets.items()
            if now - bucket["last_update"] > 3600
        ]
        for key in old_keys:
            del self.buckets[key]


# Global rate limiters
auth_limiter = RateLimiter(requests_per_minute=10)  # Strict for auth
api_limiter = RateLimiter(requests_per_minute=100)  # Standard for API
anonymous_limiter = RateLimiter(requests_per_minute=20)  # Permissive for anonymous


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits."""

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for non-API routes
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        # Get identifier (API key or IP)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            identifier = auth_header[7:]  # Use API key as identifier
            limiter = api_limiter
        else:
            identifier = request.client.host if request.client else "unknown"
            limiter = anonymous_limiter

        # Auth endpoints get stricter limits
        if "/auth/" in request.url.path:
            limiter = auth_limiter

        # Check rate limit
        if not limiter.is_allowed(identifier):
            logger.warning(
                f"Rate limit exceeded for {identifier} on {request.url.path}",
                extra={"endpoint": request.url.path, "client": identifier}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Maximum requests per minute exceeded.",
                headers={"Retry-After": "60"}
            )

        # Periodically cleanup old buckets
        if time.time() % 100 < 1:  # ~1% of requests
            limiter.cleanup_old_buckets()

        return await call_next(request)


def get_rate_limiter(limiter_type: str = "api") -> RateLimiter:
    """Get a rate limiter instance."""
    if limiter_type == "auth":
        return auth_limiter
    elif limiter_type == "anonymous":
        return anonymous_limiter
    else:
        return api_limiter
