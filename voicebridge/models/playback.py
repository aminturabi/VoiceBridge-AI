"""Playback Provider abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from voicebridge.pipeline.contracts.schemas import PlaybackRequest, PlaybackResponse


class BasePlayback(ABC):
    """Abstract base class for Audio Playback providers."""

    name: str = "base_playback"

    @abstractmethod
    def play(self, request: PlaybackRequest) -> PlaybackResponse:
        """Play audio from given file path or stream."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop active playback."""
        pass
