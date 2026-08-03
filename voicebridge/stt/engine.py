"""Backward-compatibility shim for SttEngine.

Delegates all operations to SttManager and FasterWhisperBackend.
"""

from __future__ import annotations

from voicebridge.config import Config
from voicebridge.stt.base import Transcription
from voicebridge.stt.manager import SttManager
from voicebridge.stt.reliability import ReliabilityThresholds, segment_is_reliable


class SttEngine(SttManager):
    """Backward-compatible wrapper around SttManager."""

    def __init__(self, config: Config, label: str = "stt", source_lang: str | None = None):
        super().__init__(config, label=label, source_lang=source_lang)


__all__ = ["SttEngine", "SttManager", "Transcription", "ReliabilityThresholds", "segment_is_reliable"]
