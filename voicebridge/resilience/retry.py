"""Exponential Backoff Retry with Random Jitter."""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ExponentialBackoffRetry:
    """Retries a callable with exponential backoff and random jitter."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_sec: float = 0.2,
        max_delay_sec: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.base_delay_sec = base_delay_sec
        self.max_delay_sec = max_delay_sec

    def execute(self, func: Callable[[], T], trace_id: str = "unknown") -> T:
        last_error: Exception | None = None

        for attempt in range(self.max_attempts):
            try:
                return func()
            except Exception as err:
                last_error = err
                if attempt == self.max_attempts - 1:
                    break
                delay = min(self.base_delay_sec * (2 ** attempt), self.max_delay_sec)
                jittered_delay = delay + random.uniform(0, delay * 0.1)
                logger.warning(
                    "Attempt %d/%d failed (%s) for trace_id=%s. Retrying in %.2fs",
                    attempt + 1, self.max_attempts, err, trace_id, jittered_delay
                )
                time.sleep(jittered_delay)

        raise last_error or RuntimeError("Retry exhausted without exception")
