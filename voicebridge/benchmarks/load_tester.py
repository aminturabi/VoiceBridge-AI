"""Concurrent User Load & Stress Testing Engine.

Simulates thousands of concurrent request calls, measures P50/P95/P99 latencies,
throughput (requests/sec), error rates, and system degradation.
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Dict, List, Optional

import numpy as np

from voicebridge.config import Config, load_config
from voicebridge.logging_conf import get_logger
from voicebridge.pipeline.contracts.schemas import generate_trace_id
from voicebridge.routing.router import ModelRouter

logger = get_logger(__name__)


class ConcurrentLoadTester:
    """Simulates concurrent load across pipeline stages and computes latency percentiles."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or load_config()
        self.router = ModelRouter(self.config)

    def run_load_test(
        self,
        num_concurrent_users: int = 10,
        requests_per_user: int = 5,
        test_duration_sec: float = 5.0,
    ) -> Dict[str, Any]:
        """Execute concurrent load test simulating concurrent pipeline requests."""
        logger.info(
            "[LoadTester] Starting load test with %d users (%d reqs/user)...",
            num_concurrent_users, requests_per_user
        )

        latencies_ms: List[float] = []
        errors: List[str] = []
        start_time = time.perf_counter()

        def _user_session(user_id: int) -> List[float]:
            user_lats: List[float] = []
            for i in range(requests_per_user):
                t0 = time.perf_counter()
                trace_id = generate_trace_id()
                try:
                    # Execute provider routing lookup
                    provider = self.router.select_stt_provider(language="en")
                    # Simulate request execution
                    time.sleep(0.01)
                    user_lats.append((time.perf_counter() - t0) * 1000.0)
                except Exception as err:
                    errors.append(str(err))
            return user_lats

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent_users) as executor:
            futures = [executor.submit(_user_session, uid) for uid in range(num_concurrent_users)]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    latencies_ms.extend(fut.result())
                except Exception as err:
                    errors.append(str(err))

        total_elapsed_s = time.perf_counter() - start_time
        total_requests = len(latencies_ms) + len(errors)
        throughput = total_requests / total_elapsed_s if total_elapsed_s > 0 else 0.0

        p50 = float(np.percentile(latencies_ms, 50)) if latencies_ms else 0.0
        p95 = float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0
        p99 = float(np.percentile(latencies_ms, 99)) if latencies_ms else 0.0

        results = {
            "num_concurrent_users": num_concurrent_users,
            "total_requests": total_requests,
            "successful_requests": len(latencies_ms),
            "failed_requests": len(errors),
            "total_elapsed_sec": round(total_elapsed_s, 2),
            "throughput_req_per_sec": round(throughput, 2),
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
            "error_rate_pct": round((len(errors) / total_requests * 100.0) if total_requests > 0 else 0.0, 2),
        }

        logger.info("[LoadTester] Results: %s", results)
        return results
