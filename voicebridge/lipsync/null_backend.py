"""Null lip-sync backend — audio-only passthrough.

Produces no synced video; it just reports the audio clip and (if a source face
exists) hands back the static face path. Used for fast iteration on the rest of
the pipeline without paying any lip-sync cost.
"""

from __future__ import annotations

import time
from pathlib import Path

from voicebridge.config import Config
from voicebridge.lipsync.base import LipSyncBackend, LipSyncResult
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class NullBackend(LipSyncBackend):
    name = "null"

    def __init__(self, config: Config):
        self._source_face = config.path("lipsync.source_face", "assets/faces/speaker.mp4")

    def is_available(self) -> bool:
        return True

    def sync(self, audio_path: Path, direction: str, sentence_id: int) -> LipSyncResult:
        start = time.perf_counter()
        face = self._source_face if self._source_face.exists() else None
        return LipSyncResult(
            video_path=face,
            audio_path=audio_path,
            backend=self.name,
            latency_seconds=time.perf_counter() - start,
            is_synced=False,
            note="passthrough (no lip sync)",
        )
