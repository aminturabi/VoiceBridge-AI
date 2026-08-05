"""TTS Provider abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from voicebridge.pipeline.contracts.schemas import TtsRequest, TtsResponse


class BaseTTS(ABC):
    """Abstract base class for Text-To-Speech providers."""

    name: str = "base_tts"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the TTS service or engine is ready."""
        pass

    @abstractmethod
    def synthesize(self, request: TtsRequest) -> TtsResponse:
        """Synthesize text into speech audio file matching TtsRequest."""
        pass
