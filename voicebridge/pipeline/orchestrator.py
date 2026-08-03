"""Pipeline orchestrator.

Builds the shared managers once (translation, TTS, lip-sync) and spins up one
:class:`DirectionWorker` per configured direction. For a live two-way call you
run two directions (EN->AR and AR->EN); for a one-way demo, just one.

The orchestrator is transport-agnostic: it takes an ``emit`` callback for
events. The API layer passes one that fans events out to WebSocket clients; a
CLI can pass one that prints them.
"""

from __future__ import annotations

import threading
from typing import Callable

from voicebridge.audio.capture import MicrophoneSource, WavFileSource
from voicebridge.config import Config
from voicebridge.lipsync.manager import LipSyncManager
from voicebridge.logging_conf import get_logger
from voicebridge.pipeline.events import EventType, PipelineEvent
from voicebridge.pipeline.worker import DirectionSpec, DirectionWorker
from voicebridge.translation.manager import TranslationManager
from voicebridge.tts.manager import TtsManager

logger = get_logger(__name__)

EmitFn = Callable[[PipelineEvent], None]


class Orchestrator:
    """Owns shared managers and the set of direction workers."""

    def __init__(self, config: Config, emit: EmitFn | None = None):
        self._config = config
        self._emit = emit or self._default_emit
        self._stop_event = threading.Event()

        # Shared, thread-safe managers (built once).
        self._translation = TranslationManager(config)
        self._tts = TtsManager(config)
        self._lipsync = LipSyncManager(config)

        self._workers: list[DirectionWorker] = []
        self._running = False

    @staticmethod
    def _default_emit(event: PipelineEvent) -> None:
        logger.info("[%s] %s: %s", event.direction, event.type.value, event.text or event.note)

    # -- source construction ------------------------------------------------

    def _build_source(self, spec: DirectionSpec, source_kind: str, wav_path=None):
        if source_kind == "microphone":
            return MicrophoneSource(self._config, self._stop_event)
        if source_kind == "wav":
            if not wav_path:
                raise ValueError("wav source requires wav_path")
            return WavFileSource(self._config, wav_path)
        raise ValueError(f"Unknown source kind: {source_kind}")

    def add_direction(
        self,
        source_lang: str,
        target_lang: str,
        speaker: str,
        source_kind: str = "microphone",
        wav_path=None,
    ) -> None:
        """Register a translation direction with its audio source."""
        spec = DirectionSpec(source_lang=source_lang, target_lang=target_lang, speaker=speaker)
        source = self._build_source(spec, source_kind, wav_path)
        worker = DirectionWorker(
            config=self._config,
            spec=spec,
            source=source,
            translation=self._translation,
            tts=self._tts,
            lipsync=self._lipsync,
            emit=self._emit,
            stop_event=self._stop_event,
        )
        self._workers.append(worker)
        logger.info("Registered direction %s (speaker=%s, source=%s)",
                    spec.label, speaker, source_kind)

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        if not self._workers:
            raise RuntimeError("No directions registered; call add_direction() first")
        self._stop_event.clear()
        self._running = True
        self._emit(PipelineEvent(
            type=EventType.STATUS, direction="system", speaker="system",
            note=f"Pipeline started ({len(self._workers)} direction(s))",
        ))
        for worker in self._workers:
            worker.start()

    def stop(self) -> None:
        if not self._running:
            return
        logger.info("Stopping pipeline...")
        self._stop_event.set()
        for worker in self._workers:
            worker.join()
        self._running = False
        self._emit(PipelineEvent(
            type=EventType.STATUS, direction="system", speaker="system",
            note="Pipeline stopped",
        ))

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def info(self) -> dict:
        return {
            "running": self._running,
            "directions": [w._spec.label for w in self._workers],
            "translation_backends": self._translation.backend_names,
            "lipsync_backend": self._lipsync.backend_name,
        }
