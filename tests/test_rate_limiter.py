"""Unit tests for TokenBucketRateLimiter."""

from __future__ import annotations

import time
import pytest

from voicebridge.resilience.rate_limiter import TokenBucketRateLimiter


def test_rate_limiter_basic():
    limiter = TokenBucketRateLimiter(requests_per_second=10.0, burst_capacity=2)
    assert limiter.acquire(1) is True
    assert limiter.acquire(1) is True
    assert limiter.acquire(1) is False  # Capacity exceeded


def test_rate_limiter_refill():
    limiter = TokenBucketRateLimiter(requests_per_second=100.0, burst_capacity=1)
    assert limiter.acquire(1) is True
    assert limiter.acquire(1) is False

    time.sleep(0.02)
    assert limiter.acquire(1) is True
