"""Structured telemetry, Trace ID context propagation, and metric tracking."""

from __future__ import annotations

import contextvars
import time
import uuid
from typing import Any, Dict, Optional

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)

# Context variable for holding active trace_id across async and thread boundaries.
_TRACE_ID_VAR: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)


def get_current_trace_id() -> str:
    """Return active trace_id or generate a new one if none set."""
    tid = _TRACE_ID_VAR.get()
    if not tid:
        tid = str(uuid.uuid4())
        _TRACE_ID_VAR.set(tid)
    return tid


def set_current_trace_id(trace_id: str) -> None:
    """Explicitly set active trace_id."""
    _TRACE_ID_VAR.set(trace_id)


class TraceContext:
    """Context manager for tracing operations with a trace_id."""

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self._token = None

    def __enter__(self) -> TraceContext:
        self._token = _TRACE_ID_VAR.set(self.trace_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token:
            _TRACE_ID_VAR.reset(self._token)


class TelemetryTracker:
    """Collector for fine-grained stage latencies, inference times, tokens/sec, and queue wait times."""

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or get_current_trace_id()
        self.stage_latencies_ms: Dict[str, float] = {}
        self.queue_wait_times_ms: Dict[str, float] = {}
        self.model_inference_times_ms: Dict[str, float] = {}
        self.tokens_generated: int = 0
        self.audio_duration_sec: float = 0.0
        self.errors: Dict[str, str] = {}
        self.warnings: list[str] = []
        self.start_time: float = time.perf_counter()

    def record_stage_latency(self, stage_name: str, latency_ms: float) -> None:
        self.stage_latencies_ms[stage_name] = latency_ms

    def record_queue_wait(self, stage_name: str, wait_ms: float) -> None:
        self.queue_wait_times_ms[stage_name] = wait_ms

    def record_inference_time(self, model_name: str, inference_ms: float) -> None:
        self.model_inference_times_ms[model_name] = inference_ms

    def add_tokens(self, count: int) -> None:
        self.tokens_generated += count

    def set_audio_duration(self, duration_sec: float) -> None:
        self.audio_duration_sec = duration_sec

    def record_error(self, stage_name: str, error_msg: str) -> None:
        self.errors[stage_name] = error_msg
        logger.error("[%s] Trace %s Error: %s", stage_name, self.trace_id, error_msg)

    def record_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning("Trace %s Warning: %s", self.trace_id, msg)

    @property
    def total_latency_ms(self) -> float:
        return (time.perf_counter() - self.start_time) * 1000.0

    @property
    def tokens_per_sec(self) -> float:
        total_s = self.total_latency_ms / 1000.0
        return self.tokens_generated / total_s if total_s > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "stage_latencies_ms": {k: round(v, 2) for k, v in self.stage_latencies_ms.items()},
            "queue_wait_times_ms": {k: round(v, 2) for k, v in self.queue_wait_times_ms.items()},
            "model_inference_times_ms": {k: round(v, 2) for k, v in self.model_inference_times_ms.items()},
            "tokens_generated": self.tokens_generated,
            "tokens_per_sec": round(self.tokens_per_sec, 2),
            "audio_duration_sec": round(self.audio_duration_sec, 2),
            "errors": self.errors,
            "warnings": self.warnings,
        }
