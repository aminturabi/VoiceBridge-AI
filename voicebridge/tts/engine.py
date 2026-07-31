"""Edge TTS wrapper — turns translated text into an audio file.

Each call produces a uniquely-named file so concurrent directions never clash.
edge-tts is async; we expose a sync ``synthesize`` that runs its own event loop
(safe from worker threads that have no running loop).
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import edge_tts

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class TtsEngine:
    """Generate speech audio with edge-tts."""

    def __init__(self, config: Config):
        self._config = config
        self._fmt = config.get("tts.output_format", "mp3")
        self._output_root = config.path("app.output_dir")

    def _output_path(self, direction: str, sentence_id: int) -> Path:
        safe = direction.lower().replace(" ", "_").replace("->", "to")
        out_dir = self._output_root / safe
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"tts_{sentence_id}_{uuid.uuid4().hex}.{self._fmt}"

    async def _synthesize_async(self, text: str, voice: str, out_path: Path) -> None:
        communicate = edge_tts.Communicate(text, voice=voice)
        await communicate.save(str(out_path))

    def synthesize(
        self, text: str, voice: str, direction: str, sentence_id: int
    ) -> Path:
        """Synthesize ``text`` with ``voice``; return the written audio path."""
        out_path = self._output_path(direction, sentence_id)
        logger.debug("[%s] TTS -> %s (%s)", direction, out_path.name, voice)
        asyncio.run(self._synthesize_async(text, voice, out_path))
        return out_path
