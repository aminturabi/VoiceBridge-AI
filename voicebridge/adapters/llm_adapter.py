"""LLM / Translation Provider Adapter insulating core logic from translation/LLM backends."""

from __future__ import annotations

import time

from voicebridge.config import Config
from voicebridge.models.llm import BaseLLM
from voicebridge.pipeline.contracts.schemas import LlmRequest, LlmResponse
from voicebridge.translation.manager import TranslationManager


class LlmAdapter(BaseLLM):
    """Adapter wrapping TranslationManager into the BaseLLM interface."""

    def __init__(self, config: Config, manager: TranslationManager | None = None):
        self._config = config
        self._manager = manager or TranslationManager(config)
        self.name = "adapter_llm_translation"

    def is_available(self) -> bool:
        return len(self._manager.backend_names) > 0

    def process_text(self, request: LlmRequest) -> LlmResponse:
        start_t = time.perf_counter()
        translated = self._manager.translate(
            text=request.text,
            source=request.source_language,
            target=request.target_language,
        )
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        tokens_est = len(translated.split()) if translated else 0

        return LlmResponse(
            trace_id=request.trace_id,
            text=request.text,
            translated_text=translated,
            source_language=request.source_language,
            target_language=request.target_language,
            inference_time_ms=elapsed_ms,
            tokens_generated=tokens_est,
        )
