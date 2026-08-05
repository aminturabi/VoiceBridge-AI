"""STT Stage Worker transcribing audio and emitting partial & final transcripts."""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional, Tuple

import numpy as np

from voicebridge.adapters import SttAdapter
from voicebridge.config import Config
from voicebridge.pipeline.async_queue import BoundedAsyncQueue
from voicebridge.pipeline.contracts.schemas import SttRequest, SttResponse, VadResponse, generate_trace_id
from voicebridge.pipeline.events import EventType, PipelineEvent
from voicebridge.pipeline.workers.base_worker import BaseWorker


class SttWorker(BaseWorker[Tuple[VadResponse, np.ndarray], SttResponse]):
    """Worker consuming speech segments and emitting STT transcripts."""

    def __init__(
        self,
        config: Config,
        source_lang: str,
        in_queue: BoundedAsyncQueue[Tuple[VadResponse, np.ndarray]],
        out_queue: BoundedAsyncQueue[SttResponse],
        stop_event: threading.Event,
        emit_event: Optional[Callable[[PipelineEvent], None]] = None,
        adapter: Optional[SttAdapter] = None,
    ):
        super().__init__("STT", config, in_queue=in_queue, out_queue=out_queue, stop_event=stop_event)
        self.source_lang = source_lang
        self.emit_event = emit_event
        self.adapter = adapter or SttAdapter(config, label="stt_worker", source_lang=source_lang)

    def process_item(self, item: Tuple[VadResponse, np.ndarray], wait_ms: float = 0.0) -> None:
        vad_resp, audio_frame = item
        trace_id = vad_resp.trace_id or generate_trace_id()

        req = SttRequest(trace_id=trace_id, audio_source=audio_frame, source_language=self.source_lang)
        stt_resp = self.adapter.transcribe(req)

        if stt_resp.text and self.emit_event:
            # Emit partial or final transcript event to WebSocket broker
            event_type = EventType.TRANSCRIPT if stt_resp.confidence >= 1.0 else EventType.PARTIAL_TRANSCRIPT
            self.emit_event(
                PipelineEvent(
                    type=event_type,
                    direction=f"{self.source_lang.upper()}->...",
                    speaker="speaker",
                    text=stt_resp.text,
                    trace_id=stt_resp.trace_id,
                )
            )

        if stt_resp.text and self.out_queue:
            self.out_queue.put(stt_resp)
