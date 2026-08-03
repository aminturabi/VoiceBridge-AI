"""Coqui TTS provider backend implementation / stub."""

from __future__ import annotations

import uuid
from pathlib import Path

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.tts.base import TtsBackend, TtsError

logger = get_logger(__name__)


class CoquiBackend(TtsBackend):
    """Offline Coqui TTS provider backend."""

    name: str = "coqui"

    def __init__(self, config: Config):
        self._config = config
        self._fmt = config.get("tts.output_format", "wav")
        self._output_root = config.path("app.output_dir")

    def is_available(self) -> bool:
        try:
            import TTS  # noqa: F401
            return True
        except ImportError:
            return False

    def _output_path(self, direction: str, sentence_id: int) -> Path:
        safe = direction.lower().replace(" ", "_").replace("->", "to")
        out_dir = self._output_root / safe
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"tts_coqui_{sentence_id}_{uuid.uuid4().hex}.{self._fmt}"

    def synthesize(self, text: str, voice: str, direction: str, sentence_id: int) -> Path:
        if not self.is_available():
            raise TtsError("TTS package (Coqui) is not installed")

        out_path = self._output_path(direction, sentence_id)
        logger.debug("[%s] Coqui TTS -> %s", direction, out_path.name)
        # Stub implementation for Coqui TTS synthesis
        out_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        return out_path
