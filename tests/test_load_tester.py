"""Unit tests for ConcurrentLoadTester."""

from __future__ import annotations

import pytest

from voicebridge.benchmarks.load_tester import ConcurrentLoadTester


def test_load_tester_execution():
    tester = ConcurrentLoadTester()
    results = tester.run_load_test(num_concurrent_users=2, requests_per_user=2)

    assert results["total_requests"] == 4
    assert results["successful_requests"] == 4
    assert results["throughput_req_per_sec"] > 0.0
    assert results["latency_p50_ms"] >= 0.0
    assert results["latency_p95_ms"] >= 0.0
    assert results["error_rate_pct"] == 0.0
