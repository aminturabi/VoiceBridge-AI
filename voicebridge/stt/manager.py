"""STT Manager: dynamically loads and manages configured STT backends."""

from __future__ import annotations

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.stt.base import SttBackend, SttError, Transcription
from voicebridge.stt.faster_whisper_backend import FasterWhisperBackend
from voicebridge.stt.vosk_backend import VoskBackend
from voicebridge.stt.whisper_api_backend import WhisperApiBackend

logger = get_logger(__name__)

_BACKEND_REGISTRY: dict[str, type[SttBackend]] = {
    "faster-whisper": FasterWhisperBackend,
    "whisper-api": WhisperApiBackend,
    "vosk": VoskBackend,
}


class SttManager:
    """Manages active STT backend and provides transcription service."""

    def __init__(self, config: Config, label: str = "stt", source_lang: str | None = None):
        self._config = config
        self._label = label
        self._source_lang = source_lang
        requested_provider = config.get("stt.provider", "faster-whisper")

        self._backend = self._select_backend(requested_provider)
        logger.info("[%s] Selected STT provider: %s", self._label, self._backend.name)

    def _select_backend(self, requested: str) -> SttBackend:
        # 1. Try requested provider
        backend_cls = _BACKEND_REGISTRY.get(requested)
        if backend_cls is not None:
            backend = backend_cls(self._config, label=self._label, source_lang=self._source_lang)
            if backend.is_available():
                return backend

        # 2. Fall back to faster-whisper if requested failed
        if requested != "faster-whisper":
            logger.warning("[%s] Requested STT provider %r unavailable; falling back to faster-whisper", self._label, requested)
            fw_cls = _BACKEND_REGISTRY["faster-whisper"]
            backend = fw_cls(self._config, label=self._label, source_lang=self._source_lang)
            if backend.is_available():
                return backend

        # 3. Fall back to any available backend
        for name, cls in _BACKEND_REGISTRY.items():
            b = cls(self._config, label=self._label, source_lang=self._source_lang)
            if b.is_available():
                logger.warning("[%s] Using fallback STT provider: %s", self._label, name)
                return b

        raise SttError(f"[{self._label}] No STT backends available!")

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @property
    def model(self):
        return getattr(self._backend, "model", None)

    @property
    def device(self):
        return getattr(self._backend, "device", "cpu")

    @property
    def model_size(self):
        return getattr(self._backend, "model_size", "unknown")

    def transcribe(self, audio_source) -> Transcription:
        return self._backend.transcribe(audio_source)
