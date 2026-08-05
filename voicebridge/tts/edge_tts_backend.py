"""Edge-TTS provider backend implementation."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.resilience.retry import ExponentialBackoffRetry
from voicebridge.tts.base import TtsBackend, TtsError

logger = get_logger(__name__)


class EdgeTtsBackend(TtsBackend):
    """Microsoft Neural TTS provider backend."""

    name: str = "edge-tts"
    display_name: str = "Microsoft Neural TTS"


    def __init__(self, config: Config):
        self._config = config
        self._fmt = config.get("tts.output_format", "mp3")
        self._output_root = config.path("app.output_dir")

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def _output_path(self, direction: str, sentence_id: int) -> Path:
        safe = direction.lower().replace(" ", "_").replace("->", "to")
        out_dir = self._output_root / safe
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"tts_{sentence_id}_{uuid.uuid4().hex}.{self._fmt}"

    async def _synthesize_async(self, text: str, voice: str, out_path: Path) -> None:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice=voice)
        await communicate.save(str(out_path))

    def synthesize(self, text: str, voice: str, direction: str, sentence_id: int) -> Path:
        if not self.is_available():
            raise TtsError("edge-tts package is not installed")

        out_path = self._output_path(direction, sentence_id)
        logger.debug("[%s] Edge-TTS -> %s (%s)", direction, out_path.name, voice)
        
        retry_policy = ExponentialBackoffRetry(max_attempts=3, base_delay_sec=0.5, max_delay_sec=3.0)

        def _do_synth() -> Path:
            asyncio.run(self._synthesize_async(text, voice, out_path))
            return out_path

        try:
            return retry_policy.execute(_do_synth, trace_id=f"{direction}:{sentence_id}")
        except Exception as error:  # noqa: BLE001
            raise TtsError(f"Edge-TTS synthesis failed after retries: {error}") from error

