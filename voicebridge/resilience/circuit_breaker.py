"""Circuit Breaker pattern for protecting AI providers from cascading failures."""

from __future__ import annotations

import enum
import threading
import time
from typing import Callable, Optional, TypeVar

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Provider failing; reject calls immediately
    HALF_OPEN = "HALF_OPEN"# Testing provider recovery


class CircuitBreakerError(Exception):
    """Raised when call is attempted on an OPEN circuit breaker."""


class CircuitBreaker:
    """Thread-safe Circuit Breaker implementing CLOSED -> OPEN -> HALF_OPEN states."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_sec: float = 10.0,
        config: Optional[Config] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec

        if config:
            res_cfg = config.get("resilience.circuit_breaker", {})
            self.failure_threshold = int(res_cfg.get("failure_threshold", failure_threshold))
            self.recovery_timeout_sec = float(res_cfg.get("recovery_timeout_sec", recovery_timeout_sec))

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.perf_counter()
        self.last_failure_time = 0.0
        self._lock = threading.Lock()

    def call(self, func: Callable[[], T], trace_id: str = "unknown") -> T:
        """Execute func through the circuit breaker, tripping OPEN on repeated failures."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                now = time.perf_counter()
                if now - self.last_failure_time >= self.recovery_timeout_sec:
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now
                    logger.info("[%s CircuitBreaker] %s -> HALF_OPEN (Testing recovery)", self.name, trace_id)
                else:
                    raise CircuitBreakerError(f"[{self.name}] Circuit is OPEN for trace_id={trace_id}")

        try:
            result = func()
            self.record_success(trace_id)
            return result
        except Exception as error:
            self.record_failure(trace_id, str(error))
            raise error

    def record_success(self, trace_id: str = "unknown") -> None:
        with self._lock:
            if self.state == CircuitState.HALF_OPEN or self.failure_count > 0:
                logger.info("[%s CircuitBreaker] %s -> CLOSED (Recovered)", self.name, trace_id)
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.last_state_change = time.perf_counter()

    def record_failure(self, trace_id: str = "unknown", error_msg: str = "") -> None:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.perf_counter()

            if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.last_state_change = time.perf_counter()
                logger.error(
                    "[%s CircuitBreaker] CLOSED -> OPEN (Failures=%d threshold=%d, Error: %s) for trace_id=%s",
                    self.name, self.failure_count, self.failure_threshold, error_msg, trace_id
                )
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.last_state_change = time.perf_counter()
                logger.error(
                    "[%s CircuitBreaker] HALF_OPEN -> OPEN (Recovery test failed) for trace_id=%s",
                    self.name, trace_id
                )
