"""Unit tests for CircuitBreaker state transitions and recovery."""

from __future__ import annotations

import time
import pytest

from voicebridge.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState


def test_circuit_breaker_closed_state():
    cb = CircuitBreaker("whisper", failure_threshold=2)
    assert cb.state == CircuitState.CLOSED
    res = cb.call(lambda: "ok", trace_id="t-1")
    assert res == "ok"


def test_circuit_breaker_trips_open():
    cb = CircuitBreaker("whisper", failure_threshold=2)

    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail 1")), trace_id="t-1")

    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail 2")), trace_id="t-2")

    assert cb.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerError):
        cb.call(lambda: "ok", trace_id="t-3")


def test_circuit_breaker_half_open_recovery():
    cb = CircuitBreaker("whisper", failure_threshold=1, recovery_timeout_sec=0.05)

    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")), trace_id="t-1")

    assert cb.state == CircuitState.OPEN

    time.sleep(0.06)

    # Calling after recovery timeout transitions state to HALF_OPEN and succeeds
    res = cb.call(lambda: "recovered", trace_id="t-2")
    assert res == "recovered"
    assert cb.state == CircuitState.CLOSED
