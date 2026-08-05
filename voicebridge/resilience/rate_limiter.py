"""Token Bucket Rate Limiter for request throttle protection."""

from __future__ import annotations

import threading
import time

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded and request cannot be served."""


class TokenBucketRateLimiter:
    """Thread-safe Token Bucket Rate Limiter."""

    def __init__(self, requests_per_second: float = 50.0, burst_capacity: int = 100, config: Config | None = None):
        self.rate = requests_per_second
        self.capacity = burst_capacity

        if config:
            rl_cfg = config.get("resilience.rate_limiter", {})
            self.rate = float(rl_cfg.get("requests_per_second", requests_per_second))
            self.capacity = int(rl_cfg.get("burst_capacity", burst_capacity))

        self.tokens = float(self.capacity)
        self.last_update = time.perf_counter()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """Attempt to acquire tokens; return True if successful, False if rate limited."""
        with self._lock:
            now = time.perf_counter()
            elapsed = now - self.last_update
            self.last_update = now

            # Add newly accumulated tokens based on rate
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False
