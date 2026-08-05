"""TTS Provider Adapter insulating core logic from edge-tts/coqui backends."""

from __future__ import annotations

import time

from voicebridge.config import Config
from voicebridge.models.tts import BaseTTS
from voicebridge.pipeline.contracts.schemas import TtsRequest, TtsResponse
from voicebridge.tts.manager import TtsManager


class TtsAdapter(BaseTTS):
    """Adapter wrapping TtsManager into the BaseTTS interface."""

    def __init__(self, config: Config, manager: TtsManager | None = None):
        self._config = config
        self._manager = manager or TtsManager(config)
        self.name = f"adapter_{self._manager.backend_name}"

    def is_available(self) -> bool:
        return True

    def synthesize(self, request: TtsRequest) -> TtsResponse:
        start_t = time.perf_counter()
        res_path = self._manager.synthesize(
            text=request.text,
            voice=request.voice,
            direction=request.direction,
            sentence_id=request.sentence_id,
        )
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return TtsResponse(
            trace_id=request.trace_id,
            audio_path=str(res_path),
            duration_sec=0.0,
            inference_time_ms=elapsed_ms,
        )
