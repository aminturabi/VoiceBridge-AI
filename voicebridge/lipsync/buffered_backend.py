"""Buffered Wav2Lip backend (backward-compatibility alias)."""

from __future__ import annotations

from voicebridge.config import Config
from voicebridge.lipsync.wav2lip_backend import Wav2LipBackend


class BufferedWav2LipBackend(Wav2LipBackend):
    """Backward-compatible alias for Wav2LipBackend."""

    name = "buffered"

    def __init__(self, config: Config):
        super().__init__(config)


__all__ = ["BufferedWav2LipBackend", "Wav2LipBackend"]
