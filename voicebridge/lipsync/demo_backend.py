"""Demo lip-sync backend — plays a pre-rendered clip.

Viva-safe path. Instead of running inference live, it returns a pre-rendered
lip-synced video from ``lipsync.demo.prerendered_dir``. Selection is
deterministic (round-robins by sentence id) so a demo script is repeatable.

This exists so a live demo never stalls on CPU inference; it is clearly
labelled as demo mode in the result note and the UI.
"""

from __future__ import annotations

import time
from pathlib import Path

from voicebridge.config import Config
from voicebridge.lipsync.base import LipSyncBackend, LipSyncResult
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)

_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".avi")


class DemoBackend(LipSyncBackend):
    name = "demo"

    def __init__(self, config: Config):
        self._prerendered_dir = config.path(
            "lipsync.demo.prerendered_dir", "assets/prerendered"
        )

    def _clips(self) -> list[Path]:
        if not self._prerendered_dir.exists():
            return []
        return sorted(
            p for p in self._prerendered_dir.iterdir()
            if p.suffix.lower() in _VIDEO_EXTS
        )

    def is_available(self) -> bool:
        return len(self._clips()) > 0

    def sync(self, audio_path: Path, direction: str, sentence_id: int) -> LipSyncResult:
        start = time.perf_counter()
        clips = self._clips()

        if not clips:
            logger.warning(
                "Demo backend: no prerendered clips in %s; returning audio only",
                self._prerendered_dir,
            )
            return LipSyncResult(
                video_path=None, audio_path=audio_path, backend=self.name,
                latency_seconds=time.perf_counter() - start, is_synced=False,
                note="demo mode: no prerendered clip found",
            )

        clip = clips[sentence_id % len(clips)]
        return LipSyncResult(
            video_path=clip,
            audio_path=audio_path,
            backend=self.name,
            latency_seconds=time.perf_counter() - start,
            is_synced=True,
            note="demo mode: prerendered clip",
        )
