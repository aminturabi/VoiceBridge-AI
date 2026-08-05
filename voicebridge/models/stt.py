"""STT Provider abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from voicebridge.pipeline.contracts.schemas import SttRequest, SttResponse


class BaseSTT(ABC):
    """Abstract base class for Speech-To-Text providers."""

    name: str = "base_stt"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if dependencies and models are loaded/available."""
        pass

    @abstractmethod
    def transcribe(self, request: SttRequest) -> SttResponse:
        """Transcribe audio specified by SttRequest into SttResponse."""
        pass
