"""Provider Health Monitor tracking provider availability, latencies, and system load."""

from __future__ import annotations

import threading
import time
from typing import Dict

import psutil

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class ProviderHealthMonitor:
    """Monitors provider response times, failure counts, and system CPU/RAM/GPU load."""

    _instance: ProviderHealthMonitor | None = None
    _lock = threading.Lock()

    def __init__(self, config: Config | None = None):
        self.config = config
        self.provider_latencies_ms: Dict[str, float] = {}
        self.provider_errors: Dict[str, int] = {}
        self.last_health_check: Dict[str, float] = {}

    @classmethod
    def get_instance(cls, config: Config | None = None) -> ProviderHealthMonitor:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def record_latency(self, provider_name: str, latency_ms: float) -> None:
        with self._lock:
            self.provider_latencies_ms[provider_name] = latency_ms
            self.last_health_check[provider_name] = time.perf_counter()

    def record_error(self, provider_name: str) -> None:
        with self._lock:
            self.provider_errors[provider_name] = self.provider_errors.get(provider_name, 0) + 1

    def get_health_score(self, provider_name: str) -> float:
        """Calculate health score from 0.0 (unhealthy) to 1.0 (perfect health)."""
        with self._lock:
            errors = self.provider_errors.get(provider_name, 0)
            avg_lat = self.provider_latencies_ms.get(provider_name, 100.0)

            # System resource pressure penalty
            cpu_pct = psutil.cpu_percent()
            cpu_penalty = (cpu_pct / 100.0) * 0.2 if cpu_pct > 80.0 else 0.0

            # Error penalty
            error_penalty = min(1.0, errors * 0.25)

            score = max(0.0, 1.0 - error_penalty - cpu_penalty)
            return round(score, 2)
