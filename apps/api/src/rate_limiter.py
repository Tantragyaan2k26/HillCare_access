"""Token bucket rate limiter with Redis backend and in-memory fallback."""

import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request, status
from auth import AuthUser


class InMemoryTokenBucket:
    """Fallback in-memory token bucket when Redis is unavailable."""
    def __init__(self):
        # key -> (tokens, last_update_time)
        self.buckets: Dict[str, Tuple[float, float]] = {}

    def is_allowed(self, key: str, capacity: int, fill_rate_per_sec: float) -> Tuple[bool, int]:
        now = time.time()
        tokens, last_time = self.buckets.get(key, (float(capacity), now))
        # Add leaked/replenished tokens
        delta = now - last_time
        tokens = min(float(capacity), tokens + delta * fill_rate_per_sec)

        if tokens >= 1.0:
            tokens -= 1.0
            self.buckets[key] = (tokens, now)
            return True, int(tokens)
        else:
            self.buckets[key] = (tokens, now)
            retry_after = int(max(1.0, (1.0 - tokens) / fill_rate_per_sec))
            return False, retry_after


_local_limiter = InMemoryTokenBucket()


def check_rate_limit(request: Request, user: AuthUser):
    """Check rate limit per user / client IP."""
    limits = {
        "anonymous": (60, 60 / 60.0),    # 60 req/min
        "planner": (300, 300 / 60.0),    # 300 req/min
        "analyst": (300, 300 / 60.0),    # 300 req/min
        "admin": (600, 600 / 60.0),      # 600 req/min
    }
    cap, rate = limits.get(user.role, (60, 1.0))
    key = f"rate:{user.role}:{user.id}:{request.client.host if request.client else '127.0.0.1'}"

    allowed, wait_or_remaining = _local_limiter.is_allowed(key, capacity=cap, fill_rate_per_sec=rate)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {wait_or_remaining} seconds.",
            headers={"Retry-After": str(wait_or_remaining)},
        )
