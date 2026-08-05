"""LLM / Translation Stage Worker translating transcripts into text chunks."""

from __future__ import annotations

import threading
from typing import Callable, Optional

from voicebridge.adapters import LlmAdapter
from voicebridge.config import Config
from voicebridge.pipeline.async_queue import BoundedAsyncQueue
from voicebridge.pipeline.buffer import SentenceBuffer
from voicebridge.pipeline.contracts.schemas import LlmRequest, LlmResponse, SttResponse
from voicebridge.pipeline.events import EventType, PipelineEvent
from voicebridge.pipeline.workers.base_worker import BaseWorker


class LlmWorker(BaseWorker[SttResponse, LlmResponse]):
    """Worker handling buffer aggregation & translation token/sentence chunking."""

    def __init__(
        self,
        config: Config,
        source_lang: str,
        target_lang: str,
        in_queue: BoundedAsyncQueue[SttResponse],
        out_queue: BoundedAsyncQueue[LlmResponse],
        stop_event: threading.Event,
        emit_event: Optional[Callable[[PipelineEvent], None]] = None,
        adapter: Optional[LlmAdapter] = None,
    ):
        super().__init__("LLM", config, in_queue=in_queue, out_queue=out_queue, stop_event=stop_event)
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.emit_event = emit_event
        self.buffer = SentenceBuffer(config)
        self.adapter = adapter or LlmAdapter(config)

    def process_item(self, item: SttResponse, wait_ms: float = 0.0) -> None:
        sentences = self.buffer.add(item.text)

        for sentence in sentences:
            req = LlmRequest(
                trace_id=item.trace_id,
                text=sentence,
                source_language=self.source_lang,
                target_language=self.target_lang,
            )
            llm_resp = self.adapter.process_text(req)

            if llm_resp.translated_text and self.emit_event:
                self.emit_event(
                    PipelineEvent(
                        type=EventType.TRANSLATION,
                        direction=f"{self.source_lang.upper()}->{self.target_lang.upper()}",
                        speaker="speaker",
                        text=sentence,
                        translated_text=llm_resp.translated_text,
                        trace_id=llm_resp.trace_id,
                    )
                )

            if llm_resp.translated_text and self.out_queue:
                self.out_queue.put(llm_resp)
