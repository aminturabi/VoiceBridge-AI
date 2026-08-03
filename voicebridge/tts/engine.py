"""Backward-compatibility shim for TtsEngine.

Delegates all operations to TtsManager.
"""

from __future__ import annotations

from voicebridge.config import Config
from voicebridge.tts.manager import TtsManager


class TtsEngine(TtsManager):
    """Backward-compatible wrapper around TtsManager."""

    def __init__(self, config: Config):
        super().__init__(config)


__all__ = ["TtsEngine", "TtsManager"]
