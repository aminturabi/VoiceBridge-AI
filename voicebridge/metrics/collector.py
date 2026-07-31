"""Stage and End-to-End Latency Metrics Collector.

Measures precise timing across all pipeline stages:
1. Audio Capture
2. Voice Activity Detection (VAD)
3. Speech-to-Text (STT)
4. Sentence Buffer
5. Translation
6. Text-to-Speech (TTS)
7. Lip Sync Generation
8. Playback

Provides statistical calculations (Avg, Min, Max, Median, P95, StdDev) and
throughput performance metrics.
"""

from __future__ import annotations

import math
import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class UtteranceMetric:
    """Timing and performance metrics for a single utterance processing pass."""

    session_id: str
    direction: str
    sentence_id: int
    text: str
    translated_text: str
    source_lang: str
    target_lang: str
    # Per-stage execution times in milliseconds
    stage_latencies_ms: Dict[str, float] = field(default_factory=dict)
    # End-to-end total latency in milliseconds
    total_latency_ms: float = 0.0
    # Audio input length in seconds
    audio_duration_sec: float = 0.0
    # Lip-sync rendering stats
    lip_sync_backend: str = "demo"
    is_synced: bool = False
    fps: float = 0.0
    frames_rendered: int = 0
    video_duration_sec: float = 0.0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "direction": self.direction,
            "sentence_id": self.sentence_id,
            "text": self.text,
            "translated_text": self.translated_text,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "stage_latencies_ms": {k: round(v, 2) for k, v in self.stage_latencies_ms.items()},
            "total_latency_ms": round(self.total_latency_ms, 2),
            "audio_duration_sec": round(self.audio_duration_sec, 2),
            "lip_sync_backend": self.lip_sync_backend,
            "is_synced": self.is_synced,
            "fps": round(self.fps, 2),
            "frames_rendered": self.frames_rendered,
            "video_duration_sec": round(self.video_duration_sec, 2),
            "error": self.error,
            "timestamp": self.timestamp,
        }


class StageTimer:
    """Context manager for measuring the execution time of a pipeline stage in milliseconds."""

    def __init__(self, callback: Optional[Callable[[float], None]] = None):
        self.callback = callback
        self.start_time: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> StageTimer:
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0
        if self.callback:
            self.callback(self.elapsed_ms)


class MetricsCollector:
    """Thread-safe collector for pipeline performance metrics."""

    _instance: Optional[MetricsCollector] = None
    _lock = threading.Lock()

    def __init__(self):
        self._metrics_lock = threading.Lock()
        self._records: List[UtteranceMetric] = []
        self._active_sessions: set = set()
        self._start_time: float = time.time()

    @classmethod
    def get_instance(cls) -> MetricsCollector:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = cls()

    def record_utterance(self, metric: UtteranceMetric) -> None:
        with self._metrics_lock:
            self._records.append(metric)
            if metric.session_id:
                self._active_sessions.add(metric.session_id)

    def register_session(self, session_id: str) -> None:
        with self._metrics_lock:
            self._active_sessions.add(session_id)

    def unregister_session(self, session_id: str) -> None:
        with self._metrics_lock:
            self._active_sessions.discard(session_id)

    def get_active_sessions_count(self) -> int:
        with self._metrics_lock:
            return len(self._active_sessions)

    def get_records(self) -> List[UtteranceMetric]:
        with self._metrics_lock:
            return list(self._records)

    def get_stage_averages(self) -> Dict[str, float]:
        """Calculates average latency in milliseconds for each pipeline stage."""
        with self._metrics_lock:
            if not self._records:
                return {}
            stage_totals: Dict[str, float] = {}
            stage_counts: Dict[str, int] = {}
            for r in self._records:
                for stage, lat in r.stage_latencies_ms.items():
                    stage_totals[stage] = stage_totals.get(stage, 0.0) + lat
                    stage_counts[stage] = stage_counts.get(stage, 0) + 1
            return {
                stage: round(stage_totals[stage] / stage_counts[stage], 2)
                for stage in stage_totals
            }

    def get_e2e_latency_stats(self) -> Dict[str, float]:
        """Calculates End-to-End latency statistical breakdown."""
        with self._metrics_lock:
            latencies = [r.total_latency_ms for r in self._records if r.total_latency_ms > 0]
            if not latencies:
                return {
                    "avg_ms": 0.0,
                    "min_ms": 0.0,
                    "max_ms": 0.0,
                    "median_ms": 0.0,
                    "p95_ms": 0.0,
                    "std_dev_ms": 0.0,
                    "count": 0,
                }
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            p95_index = max(0, math.ceil(0.95 * n) - 1)
            std_dev = statistics.stdev(sorted_lat) if n > 1 else 0.0
            return {
                "avg_ms": round(statistics.mean(sorted_lat), 2),
                "min_ms": round(sorted_lat[0], 2),
                "max_ms": round(sorted_lat[-1], 2),
                "median_ms": round(statistics.median(sorted_lat), 2),
                "p95_ms": round(sorted_lat[p95_index], 2),
                "std_dev_ms": round(std_dev, 2),
                "count": n,
            }

    def get_throughput_stats(self) -> Dict[str, float]:
        """Calculates throughput statistics (RPS, sentences/min, audio-minutes/min)."""
        with self._metrics_lock:
            elapsed_sec = max(1.0, time.time() - self._start_time)
            elapsed_min = elapsed_sec / 60.0
            count = len(self._records)
            total_audio_sec = sum(r.audio_duration_sec for r in self._records)
            total_audio_min = total_audio_sec / 60.0

            return {
                "requests_per_sec": round(count / elapsed_sec, 3),
                "sentences_per_min": round(count / elapsed_min, 2),
                "audio_min_per_min": round(total_audio_min / elapsed_min, 2),
                "total_sentences": count,
                "total_audio_seconds": round(total_audio_sec, 2),
                "elapsed_seconds": round(elapsed_sec, 2),
            }

    def get_fps_stats(self) -> Dict[str, float]:
        """Calculates lip-sync rendering FPS statistics."""
        with self._metrics_lock:
            fps_values = [r.fps for r in self._records if r.fps > 0]
            if not fps_values:
                return {
                    "avg_fps": 0.0,
                    "min_fps": 0.0,
                    "max_fps": 0.0,
                    "count": 0,
                }
            return {
                "avg_fps": round(statistics.mean(fps_values), 2),
                "min_fps": round(min(fps_values), 2),
                "max_fps": round(max(fps_values), 2),
                "count": len(fps_values),
            }

    def clear(self) -> None:
        with self._metrics_lock:
            self._records.clear()
            self._active_sessions.clear()
            self._start_time = time.time()
