"""STT Backend abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Transcription:
    """Result of transcribing one audio chunk."""

    text: str
    language: str
    reliable_segments: int
    total_segments: int


class SttError(Exception):
    """Raised when an STT backend fails to transcribe audio."""


class SttBackend(ABC):
    """Abstract base class for all STT provider backends."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the backend is available (dependencies installed, models ready)."""

    @abstractmethod
    def transcribe(self, audio_source: str | object, language: str | None = None) -> Transcription:
        """Transcribe an audio file or array and return a :class:`Transcription`."""
