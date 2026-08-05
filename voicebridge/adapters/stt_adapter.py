"""STT Provider Adapter insulating core logic from Whisper/Vosk specifics."""

from __future__ import annotations

import time

from voicebridge.config import Config
from voicebridge.models.stt import BaseSTT
from voicebridge.pipeline.contracts.schemas import SttErrorSchema, SttRequest, SttResponse
from voicebridge.stt.manager import SttManager


class SttAdapter(BaseSTT):
    """Adapter wrapping SttManager into the BaseSTT interface."""

    def __init__(self, config: Config, label: str = "stt", source_lang: str | None = None, manager: SttManager | None = None):
        self._config = config
        self._label = label
        self._manager = manager or SttManager(config, label=label, source_lang=source_lang)
        self.name = f"adapter_{self._manager.backend_name}"

    def is_available(self) -> bool:
        return True

    def transcribe(self, request: SttRequest) -> SttResponse:
        start_t = time.perf_counter()
        result = self._manager.transcribe(request.audio_source, language=request.source_language)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return SttResponse(
            trace_id=request.trace_id,
            text=result.text,
            detected_language=result.language,
            confidence=1.0 if result.total_segments > 0 and result.reliable_segments > 0 else 0.0,
            reliable_segments=result.reliable_segments,
            total_segments=result.total_segments,
            inference_time_ms=elapsed_ms,
        )
