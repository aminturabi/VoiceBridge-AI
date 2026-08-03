"""TTS Backend abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TtsError(Exception):
    """Raised when TTS synthesis fails."""


class TtsBackend(ABC):
    """Abstract base class for TTS provider backends."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the TTS backend is available."""

    @abstractmethod
    def synthesize(self, text: str, voice: str, direction: str, sentence_id: int) -> Path:
        """Synthesize text into speech audio and return the written Path."""
