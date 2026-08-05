"""Playback Provider Adapter insulating core logic from audio device playback."""

from __future__ import annotations

from voicebridge.audio.playback import AudioPlayer
from voicebridge.config import Config
from voicebridge.models.playback import BasePlayback
from voicebridge.pipeline.contracts.schemas import PlaybackRequest, PlaybackResponse


class PlaybackAdapter(BasePlayback):
    """Adapter wrapping AudioPlayer into the BasePlayback interface."""

    def __init__(self, config: Config, player: AudioPlayer | None = None):
        self._config = config
        self._player = player or AudioPlayer(config)
        self.name = "adapter_audio_player"

    def play(self, request: PlaybackRequest) -> PlaybackResponse:
        self._player.play(request.audio_path)
        return PlaybackResponse(
            trace_id=request.trace_id,
            success=True,
        )

    def stop(self) -> None:
        self._player.stop()
