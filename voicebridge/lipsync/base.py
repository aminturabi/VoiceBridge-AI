"""Lip-sync backend interface.

A backend takes a TTS audio clip and produces a talking-head video clip whose
mouth is synced to that audio. The three concrete backends trade off realism
against speed on CPU-only hardware:

* ``null``     — no sync; returns a static/looping face video with the audio
                 muxed in. Fastest; for iterating on the rest of the pipeline.
* ``demo``     — plays a pre-rendered lip-synced clip. Viva-safe: smooth and
                 reliable, clearly labelled as demo mode.
* ``buffered`` — real Wav2Lip inference on the short TTS segment. Genuine sync,
                 but near-real-time (buffered) on CPU, not truly real-time.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LipSyncResult:
    """Outcome of a lip-sync request."""

    video_path: Path | None
    audio_path: Path
    backend: str
    # Extra latency this backend added (seconds), for honest reporting.
    latency_seconds: float
    # True if a real synced video was produced (vs. passthrough/demo).
    is_synced: bool
    note: str = ""


class LipSyncError(Exception):
    """Raised when a backend cannot produce output."""


class LipSyncBackend(ABC):
    """Turns a (translated) audio clip into a lip-synced video clip."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can run (weights present, deps installed)."""

    @abstractmethod
    def sync(self, audio_path: Path, direction: str, sentence_id: int) -> LipSyncResult:
        """Produce a lip-synced clip for ``audio_path``."""
