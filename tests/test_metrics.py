"""Unit and Integration Tests for Performance Benchmarking & Monitoring System."""

from __future__ import annotations

import json
import time
from pathlib import Path
import pytest

from voicebridge.config import Config, load_config
from voicebridge.metrics.collector import MetricsCollector, StageTimer, UtteranceMetric
from voicebridge.metrics.logger import StructuredMetricsLogger
from voicebridge.metrics.model_tracker import ModelLoadTracker
from voicebridge.metrics.reporter import PerformanceReporter
from voicebridge.metrics.resource_monitor import ResourceMonitor


@pytest.fixture(autouse=True)
def reset_metrics_singletons():
    MetricsCollector.reset_instance()
    ModelLoadTracker.reset_instance()
    yield
    MetricsCollector.reset_instance()
    ModelLoadTracker.reset_instance()


def test_stage_timer():
    recorded_lat = []
    with StageTimer(callback=lambda lat: recorded_lat.append(lat)):
        time.sleep(0.01)

    assert len(recorded_lat) == 1
    assert recorded_lat[0] >= 5.0  # ms


def test_metrics_collector_e2e_and_stage_stats():
    collector = MetricsCollector.get_instance()

    m1 = UtteranceMetric(
        session_id="s1",
        direction="EN->AR",
        sentence_id=1,
        text="Hello world",
        translated_text="مرحبا بالعالم",
        source_lang="en",
        target_lang="ar",
        stage_latencies_ms={
            "Audio Capture": 20.0,
            "STT": 400.0,
            "Translation": 80.0,
            "TTS": 300.0,
            "Lip Sync": 500.0,
        },
        total_latency_ms=1300.0,
        audio_duration_sec=3.0,
        fps=25.0,
    )
    m2 = UtteranceMetric(
        session_id="s1",
        direction="EN->AR",
        sentence_id=2,
        text="How are you?",
        translated_text="كيف حالك؟",
        source_lang="en",
        target_lang="ar",
        stage_latencies_ms={
            "Audio Capture": 18.0,
            "STT": 350.0,
            "Translation": 70.0,
            "TTS": 280.0,
            "Lip Sync": 450.0,
        },
        total_latency_ms=1168.0,
        audio_duration_sec=2.5,
        fps=25.0,
    )

    collector.record_utterance(m1)
    collector.record_utterance(m2)

    stages = collector.get_stage_averages()
    assert stages["Audio Capture"] == 19.0
    assert stages["STT"] == 375.0

    e2e = collector.get_e2e_latency_stats()
    assert e2e["count"] == 2
    assert e2e["min_ms"] == 1168.0
    assert e2e["max_ms"] == 1300.0
    assert e2e["avg_ms"] == 1234.0

    tp = collector.get_throughput_stats()
    assert tp["total_sentences"] == 2
    assert tp["total_audio_seconds"] == 5.5


def test_resource_monitor(tmp_path: Path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    (temp_dir / "sample.wav").write_bytes(b"0" * 1024)

    monitor = ResourceMonitor(sample_interval_sec=0.1, temp_dir=temp_dir)
    snapshot = monitor.sample_now()

    assert snapshot.cpu_percent >= 0.0
    assert snapshot.ram_mb > 0.0
    assert snapshot.temp_dir_size_mb > 0.0

    summary = monitor.get_summary()
    assert "cpu" in summary
    assert "memory" in summary
    assert "disk" in summary


def test_model_load_tracker():
    tracker = ModelLoadTracker.get_instance()

    hit1 = tracker.record_load("stt", "whisper_tiny_cpu", load_time_ms=1200.0, device="cpu")
    assert hit1 is False  # Initial load, cache miss

    hit2 = tracker.record_load("stt", "whisper_tiny_cpu", load_time_ms=5.0, device="cpu")
    assert hit2 is True   # Subsequent load, cache hit

    summary = tracker.get_summary()
    assert summary["cache_hits"] == 1
    assert summary["cache_misses"] == 1
    assert len(summary["models"]) == 2


def test_structured_metrics_logger(tmp_path: Path):
    config = load_config()
    log_file = tmp_path / "test_performance.jsonl"
    logger = StructuredMetricsLogger(config, log_path=log_file)

    metric = UtteranceMetric(
        session_id="s_test",
        direction="EN->AR",
        sentence_id=1,
        text="Testing logger",
        translated_text="اختبار المسجل",
        source_lang="en",
        target_lang="ar",
        stage_latencies_ms={"STT": 250.0},
        total_latency_ms=500.0,
    )
    logger.log_utterance(metric)

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["session_id"] == "s_test"
    assert data["text"] == "Testing logger"


def test_performance_reporter(tmp_path: Path):
    collector = MetricsCollector.get_instance()
    m = UtteranceMetric(
        session_id="s_rep",
        direction="EN->AR",
        sentence_id=1,
        text="Report test",
        translated_text="اختبار التقرير",
        source_lang="en",
        target_lang="ar",
        stage_latencies_ms={"Lip Sync": 600.0, "STT": 300.0},
        total_latency_ms=900.0,
        fps=25.0,
    )
    collector.record_utterance(m)

    reporter = PerformanceReporter(collector=collector)
    bottlenecks = reporter.analyze_bottlenecks()
    assert bottlenecks["slowest_stage"] == "Lip Sync"

    md_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "report.csv"

    reporter.export_markdown(md_path)
    reporter.export_json(json_path)
    reporter.export_csv(csv_path)

    assert md_path.exists()
    assert json_path.exists()
    assert csv_path.exists()

    assert "VoiceBridge AI Performance & Benchmark Report" in md_path.read_text(encoding="utf-8")
