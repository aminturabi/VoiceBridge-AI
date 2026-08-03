"""Whisper API STT Backend stub/provider."""

from __future__ import annotations

import os

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.stt.base import SttBackend, SttError, Transcription

logger = get_logger(__name__)


class WhisperApiBackend(SttBackend):
    """Remote OpenAI Whisper API provider backend."""

    name: str = "whisper-api"

    def __init__(self, config: Config, label: str = "stt", source_lang: str | None = None):
        self._config = config
        self._label = label
        self._source_lang = source_lang
        self._api_key = os.environ.get("OPENAI_API_KEY") or config.get("stt.whisper_api.api_key", None)

    def is_available(self) -> bool:
        return bool(self._api_key)

    def transcribe(self, audio_source) -> Transcription:
        if not self.is_available():
            raise SttError("OPENAI_API_KEY is not set for WhisperApiBackend")

        # Stub implementation for remote API calls
        logger.info("[%s] Transcribing audio via Whisper API", self._label)
        return Transcription(
            text="",
            language=self._source_lang or "en",
            reliable_segments=0,
            total_segments=0,
        )
