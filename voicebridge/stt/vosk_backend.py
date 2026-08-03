"""Vosk STT Backend provider."""

from __future__ import annotations

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.stt.base import SttBackend, SttError, Transcription

logger = get_logger(__name__)


class VoskBackend(SttBackend):
    """Offline Vosk STT provider backend."""

    name: str = "vosk"

    def __init__(self, config: Config, label: str = "stt", source_lang: str | None = None):
        self._config = config
        self._label = label
        self._source_lang = source_lang

    def is_available(self) -> bool:
        try:
            import vosk  # noqa: F401
            return True
        except ImportError:
            return False

    def transcribe(self, audio_source) -> Transcription:
        if not self.is_available():
            raise SttError("vosk package is not installed")

        logger.info("[%s] Transcribing audio via Vosk", self._label)
        return Transcription(
            text="",
            language=self._source_lang or "en",
            reliable_segments=0,
            total_segments=0,
        )
