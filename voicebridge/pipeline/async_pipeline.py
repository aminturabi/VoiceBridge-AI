"""Async Pipeline Orchestrator linking stage workers with bounded queues."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.pipeline.async_queue import BoundedAsyncQueue
from voicebridge.pipeline.events import PipelineEvent
from voicebridge.pipeline.workers import LlmWorker, PlaybackWorker, SttWorker, TtsWorker, VadWorker

logger = get_logger(__name__)


class AsyncPipelineOrchestrator:
    """Async pipeline linking independent workers with bounded queues and backpressure."""

    def __init__(
        self,
        config: Config,
        source_lang: str,
        target_lang: str,
        source: Any,
        emit_event: Optional[Callable[[PipelineEvent], None]] = None,
    ):
        self.config = config
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.source = source
        self.emit_event = emit_event

        self.stop_event = threading.Event()
        self.is_running = False

        # 1. Initialize Bounded Async Queues
        stt_qsize = config.queue_size("stt", 10)
        llm_qsize = config.queue_size("llm", 10)
        tts_qsize = config.queue_size("tts", 10)
        playback_qsize = config.queue_size("playback", 20)

        self.stt_queue = BoundedAsyncQueue("stt_queue", maxsize=stt_qsize, config=config)
        self.llm_queue = BoundedAsyncQueue("llm_queue", maxsize=llm_qsize, config=config)
        self.tts_queue = BoundedAsyncQueue("tts_queue", maxsize=tts_qsize, config=config)
        self.playback_queue = BoundedAsyncQueue("playback_queue", maxsize=playback_qsize, config=config)

        # 2. Instantiate Stage Workers
        self.vad_worker = VadWorker(config, source, self.stt_queue, self.stop_event)
        self.stt_worker = SttWorker(config, source_lang, self.stt_queue, self.llm_queue, self.stop_event, emit_event)
        self.llm_worker = LlmWorker(config, source_lang, target_lang, self.llm_queue, self.tts_queue, self.stop_event, emit_event)
        self.tts_worker = TtsWorker(config, target_lang, self.tts_queue, self.playback_queue, self.stop_event)
        self.playback_worker = PlaybackWorker(config, self.playback_queue, self.stop_event, emit_event)

        self.workers = [
            self.vad_worker,
            self.stt_worker,
            self.llm_worker,
            self.tts_worker,
            self.playback_worker,
        ]

    def start(self) -> None:
        """Start all worker threads."""
        logger.info("[AsyncPipeline] Starting 5 stage workers...")
        self.stop_event.clear()
        for w in self.workers:
            w.start()
        self.is_running = True

    def stop(self, timeout: float = 3.0) -> None:
        """Gracefully stop all worker threads."""
        logger.info("[AsyncPipeline] Stopping worker threads...")
        self.stop_event.set()
        for w in self.workers:
            w.cancel()
            w.join(timeout=timeout)
        self.is_running = False

    def get_status(self) -> Dict[str, Any]:
        """Return queue depths, worker utilization, and throughput telemetry."""
        return {
            "is_running": self.is_running,
            "queues": {
                "stt_queue": {"size": self.stt_queue.qsize, "overloads": self.stt_queue.overload_count},
                "llm_queue": {"size": self.llm_queue.qsize, "overloads": self.llm_queue.overload_count},
                "tts_queue": {"size": self.tts_queue.qsize, "overloads": self.tts_queue.overload_count},
                "playback_queue": {"size": self.playback_queue.qsize, "overloads": self.playback_queue.overload_count},
            },
            "worker_utilization": {
                w.name: round(w.utilization_percent, 2) for w in self.workers
            },
            "items_processed": {
                w.name: w.items_processed for w in self.workers
            },
        }
