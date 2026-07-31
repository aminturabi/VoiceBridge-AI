"""Model Loading & Initialization Metrics Tracker.

Measures startup times for all pipeline models:
- Whisper STT model loading time (per device/direction)
- Translation backends initialization time (Google / Argos)
- TTS engine initialization
- Wav2Lip lip-sync backend loading time
- Total system startup time

Tracks model caching hits and misses.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


@dataclass
class ModelLoadMetric:
    """Load duration and device information for a single model or backend."""

    component: str  # "stt", "translation", "tts", "lipsync"
    name: str       # e.g. "whisper_tiny_cpu", "argos_en_ar", "edge_tts", "wav2lip_gan"
    load_time_ms: float
    device: str = "cpu"
    cache_hit: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "name": self.name,
            "load_time_ms": round(self.load_time_ms, 2),
            "device": self.device,
            "cache_hit": self.cache_hit,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class ModelLoadTracker:
    """Thread-safe tracker for model loading and initialization latency."""

    _instance: Optional[ModelLoadTracker] = None
    _lock = threading.Lock()

    def __init__(self):
        self._tracker_lock = threading.Lock()
        self._records: List[ModelLoadMetric] = []
        self._loaded_models: set = set()
        self._system_start_time: float = time.time()

    @classmethod
    def get_instance(cls) -> ModelLoadTracker:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = cls()

    def record_load(
        self,
        component: str,
        name: str,
        load_time_ms: float,
        device: str = "cpu",
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Records a model load event; returns True if cache hit, False if fresh load."""
        with self._tracker_lock:
            cache_hit = name in self._loaded_models
            if not cache_hit:
                self._loaded_models.add(name)

            metric = ModelLoadMetric(
                component=component,
                name=name,
                load_time_ms=load_time_ms,
                device=device,
                cache_hit=cache_hit,
                details=details or {},
            )
            self._records.append(metric)
            logger.info(
                "Model [%s/%s] loaded in %.1fms (device=%s, cache_hit=%s)",
                component, name, load_time_ms, device, cache_hit
            )
            return cache_hit

    def get_records(self) -> List[ModelLoadMetric]:
        with self._tracker_lock:
            return list(self._records)

    def get_summary(self) -> Dict[str, Any]:
        """Calculates model loading summary performance metrics."""
        with self._tracker_lock:
            if not self._records:
                return {
                    "total_startup_ms": 0.0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "models": [],
                }

            total_load_ms = sum(r.load_time_ms for r in self._records if not r.cache_hit)
            cache_hits = sum(1 for r in self._records if r.cache_hit)
            cache_misses = sum(1 for r in self._records if not r.cache_hit)

            return {
                "total_startup_ms": round(total_load_ms, 2),
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "models": [r.to_dict() for r in self._records],
            }

    def clear(self) -> None:
        with self._tracker_lock:
            self._records.clear()
            self._loaded_models.clear()
            self._system_start_time = time.time()
