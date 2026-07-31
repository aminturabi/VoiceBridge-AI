"""Structured JSON Performance Metrics Logger.

Writes detailed pipeline execution logs in structured JSON lines (.jsonl) format
containing timestamps, session IDs, language pairs, stage latencies, hardware resource
usage snapshots, and error status.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.metrics.collector import UtteranceMetric
from voicebridge.metrics.resource_monitor import ResourceSnapshot

logger = get_logger(__name__)


class StructuredMetricsLogger:
    """Writes pipeline metrics and resource logs as JSON lines."""

    def __init__(self, config: Config, log_path: Optional[Path] = None):
        self._config = config
        self._enabled = config.get("metrics.enabled", True)
        if log_path:
            self._log_path = log_path
        else:
            self._log_path = config.path("metrics.json_log_path", "logs/performance.jsonl")

        self._lock = threading.Lock()
        if self._enabled:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_utterance(
        self,
        metric: UtteranceMetric,
        resource_snapshot: Optional[ResourceSnapshot] = None,
    ) -> None:
        """Writes an utterance metrics record as a single JSON line."""
        if not self._enabled:
            return

        payload: Dict[str, Any] = metric.to_dict()
        if resource_snapshot:
            payload["resource_usage"] = resource_snapshot.to_dict()

        json_str = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            try:
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json_str + "\n")
            except Exception as err:
                logger.warning("Failed to write structured metric log: %s", err)

    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Writes an arbitrary structured event log line."""
        if not self._enabled:
            return

        payload = {
            "event_type": event_type,
            "details": details,
        }
        json_str = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            try:
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json_str + "\n")
            except Exception as err:
                logger.warning("Failed to write structured event log: %s", err)
