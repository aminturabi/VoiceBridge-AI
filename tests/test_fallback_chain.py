"""Unit tests for FallbackChain automatic multi-provider failovers."""

from __future__ import annotations

import pytest

from voicebridge.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerError
from voicebridge.routing.fallback_chain import FallbackChain


def test_fallback_chain_primary_success():
    chain = FallbackChain("test_stt")
    providers = [
        ("primary", lambda: "primary_result"),
        ("secondary", lambda: "secondary_result"),
    ]

    res = chain.execute(providers, trace_id="t-1")
    assert res == "primary_result"


def test_fallback_chain_primary_fails_secondary_succeeds():
    chain = FallbackChain("test_llm")

    def primary_fail():
        raise RuntimeError("Primary network timeout")

    providers = [
        ("primary", primary_fail),
        ("secondary", lambda: "secondary_result"),
    ]

    res = chain.execute(providers, trace_id="t-2")
    assert res == "secondary_result"


def test_fallback_chain_with_circuit_breaker_open():
    cb_primary = CircuitBreaker("primary", failure_threshold=1)
    cb_primary.record_failure("t-0", "Failed")

    chain = FallbackChain("test_cb", breakers={"primary": cb_primary})
    providers = [
        ("primary", lambda: "primary_result"),
        ("secondary", lambda: "secondary_result"),
    ]

    res = chain.execute(providers, trace_id="t-3")
    assert res == "secondary_result"
