"""Unit tests for Telemetry, Tracing context, and metric collection."""

from __future__ import annotations

import time
import pytest

from voicebridge.telemetry import (
    TelemetryTracker,
    TraceContext,
    get_current_trace_id,
    set_current_trace_id,
)


def test_trace_context_manager():
    original_id = get_current_trace_id()

    with TraceContext("explicit-trace-123") as ctx:
        assert ctx.trace_id == "explicit-trace-123"
        assert get_current_trace_id() == "explicit-trace-123"

    # Outside context, should revert or be reset
    set_current_trace_id(original_id)
    assert get_current_trace_id() == original_id


def test_telemetry_tracker_metrics():
    tracker = TelemetryTracker(trace_id="telemetry-test-id")
    time.sleep(0.01)

    tracker.record_stage_latency("VAD", 15.0)
    tracker.record_stage_latency("STT", 250.0)
    tracker.record_queue_wait("STT", 5.0)
    tracker.record_inference_time("faster-whisper", 240.0)
    tracker.add_tokens(25)
    tracker.set_audio_duration(3.5)
    tracker.record_warning("Low audio volume")

    data = tracker.to_dict()

    assert data["trace_id"] == "telemetry-test-id"
    assert data["total_latency_ms"] >= 10.0
    assert data["stage_latencies_ms"]["STT"] == 250.0
    assert data["queue_wait_times_ms"]["STT"] == 5.0
    assert data["model_inference_times_ms"]["faster-whisper"] == 240.0
    assert data["tokens_generated"] == 25
    assert data["tokens_per_sec"] > 0.0
    assert data["audio_duration_sec"] == 3.5
    assert "Low audio volume" in data["warnings"]


def test_telemetry_tracker_error_logging():
    tracker = TelemetryTracker(trace_id="error-trace-456")
    tracker.record_error("TTS", "Engine failure")

    data = tracker.to_dict()
    assert data["errors"]["TTS"] == "Engine failure"
