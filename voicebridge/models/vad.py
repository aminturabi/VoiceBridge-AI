"""VAD Provider abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from voicebridge.pipeline.contracts.schemas import VadRequest, VadResponse


class BaseVAD(ABC):
    """Abstract base class for Voice Activity Detection providers."""

    name: str = "base_vad"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the VAD model/detector is ready."""
        pass

    @abstractmethod
    def detect_speech(self, request: VadRequest) -> VadResponse:
        """Analyze audio data for speech activity."""
        pass
