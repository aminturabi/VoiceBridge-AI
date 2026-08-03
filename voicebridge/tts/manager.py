"""TTS Manager: dynamically selects TTS provider backends and integrates audio caching."""

from __future__ import annotations

import uuid
from pathlib import Path

from voicebridge.cache import AudioCache
from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.tts.base import TtsBackend, TtsError
from voicebridge.tts.coqui_backend import CoquiBackend
from voicebridge.tts.edge_tts_backend import EdgeTtsBackend

logger = get_logger(__name__)

_BACKEND_REGISTRY: dict[str, type[TtsBackend]] = {
    "edge-tts": EdgeTtsBackend,
    "coqui": CoquiBackend,
}


class TtsManager:
    """Manages TTS provider selection and cached speech synthesis."""

    def __init__(self, config: Config):
        self._config = config
        self._cache = AudioCache(config)
        self._output_root = config.path("app.output_dir")
        self._fmt = config.get("tts.output_format", "mp3")

        requested = config.get("tts.provider", "edge-tts")
        self._backend = self._select_backend(requested)
        logger.info("TTS backend selected: %s", self._backend.name)

    def _select_backend(self, requested: str) -> TtsBackend:
        cls = _BACKEND_REGISTRY.get(requested)
        if cls is not None:
            backend = cls(self._config)
            if backend.is_available():
                return backend
            logger.warning("Requested TTS backend %r unavailable; attempting fallback", requested)

        # Fallback loop
        for name, backend_cls in _BACKEND_REGISTRY.items():
            b = backend_cls(self._config)
            if b.is_available():
                logger.warning("Using fallback TTS backend: %s", name)
                return b

        raise TtsError("No TTS backends available!")

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def _target_path(self, direction: str, sentence_id: int) -> Path:
        safe = direction.lower().replace(" ", "_").replace("->", "to")
        out_dir = self._output_root / safe
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"tts_{sentence_id}_{uuid.uuid4().hex}.{self._fmt}"

    def synthesize(self, text: str, voice: str, direction: str, sentence_id: int) -> Path:
        """Synthesize text with active backend, using audio cache if available."""
        out_path = self._target_path(direction, sentence_id)

        # 1. Try audio cache hit
        if self._cache.get(text, voice, self._fmt, out_path):
            return out_path

        # 2. Perform TTS synthesis
        res_path = self._backend.synthesize(text, voice, direction, sentence_id)

        # 3. Store in audio cache
        self._cache.store(text, voice, self._fmt, res_path)

        return res_path
