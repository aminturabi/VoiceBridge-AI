"""Automatic Multi-Provider Fallback Chain for seamless failover."""

from __future__ import annotations

from typing import Callable, List, TypeVar

from voicebridge.logging_conf import get_logger
from voicebridge.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerError

logger = get_logger(__name__)

T = TypeVar("T")


class FallbackChain:
    """Executes a list of candidate providers sequentially (Primary -> Secondary -> Local)."""

    def __init__(self, chain_name: str, breakers: dict[str, CircuitBreaker] | None = None):
        self.chain_name = chain_name
        self.breakers = breakers or {}

    def execute(
        self,
        providers: List[tuple[str, Callable[[], T]]],
        trace_id: str = "unknown",
    ) -> T:
        """Attempt execution on providers in order. On failure/circuit open, fail over down chain."""
        last_error: Exception | None = None

        for idx, (p_name, p_func) in enumerate(providers):
            breaker = self.breakers.get(p_name)
            try:
                if idx > 0:
                    logger.warning(
                        "[%s FallbackChain] Failing over to candidate %d (%s) for trace_id=%s",
                        self.chain_name, idx + 1, p_name, trace_id
                    )

                if breaker:
                    return breaker.call(p_func, trace_id=trace_id)

                return p_func()
            except (CircuitBreakerError, Exception) as err:
                last_error = err
                logger.error(
                    "[%s FallbackChain] Provider %s failed (%s) for trace_id=%s. Trying next candidate...",
                    self.chain_name, p_name, err, trace_id
                )

        raise RuntimeError(
            f"[{self.chain_name}] All fallback chain candidates failed for trace_id={trace_id}. "
            f"Last error: {last_error}"
        )
