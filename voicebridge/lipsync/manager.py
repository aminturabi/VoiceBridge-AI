"""Lip-sync backend factory + fallback.

Builds the backend named in ``lipsync.backend``. If it is unavailable (e.g.
``buffered`` selected but no Wav2Lip weights) it falls back down a safe chain
so the pipeline always produces *something*:

    buffered -> demo -> null
"""

from __future__ import annotations

from pathlib import Path

from voicebridge.config import Config
from voicebridge.lipsync.base import LipSyncBackend, LipSyncError, LipSyncResult
from voicebridge.lipsync.buffered_backend import BufferedWav2LipBackend
from voicebridge.lipsync.demo_backend import DemoBackend
from voicebridge.lipsync.null_backend import NullBackend
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)

_FALLBACK_ORDER = ["buffered", "demo", "null"]

_BACKEND_REGISTRY = {
    "buffered": BufferedWav2LipBackend,
    "demo": DemoBackend,
    "null": NullBackend,
}


class LipSyncManager:
    """Selects a working lip-sync backend and runs sync requests."""

    def __init__(self, config: Config):
        self._config = config
        requested = config.get("lipsync.backend", "demo")
        self._backend = self._select(requested)
        logger.info("Lip-sync backend: %s", self._backend.name)

    def _select(self, requested: str) -> LipSyncBackend:
        # Try the requested backend first, then the remaining fallback chain.
        candidates = [requested] + [b for b in _FALLBACK_ORDER if b != requested]
        for name in candidates:
            backend_cls = _BACKEND_REGISTRY.get(name)
            if backend_cls is None:
                logger.warning("Unknown lip-sync backend %r; skipping", name)
                continue
            backend = backend_cls(self._config)
            if backend.is_available():
                if name != requested:
                    logger.warning(
                        "Requested lip-sync backend %r unavailable; using %r",
                        requested, name,
                    )
                return backend
        # NullBackend is always available, so we should never reach here.
        logger.error("No lip-sync backend available; using null")
        return NullBackend(self._config)

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def sync(self, audio_path: Path, direction: str, sentence_id: int) -> LipSyncResult:
        try:
            return self._backend.sync(audio_path, direction, sentence_id)
        except LipSyncError as error:
            logger.warning("Lip-sync failed (%s); returning audio-only", error)
            return LipSyncResult(
                video_path=None, audio_path=audio_path, backend=self._backend.name,
                latency_seconds=0.0, is_synced=False, note=f"error: {error}",
            )
