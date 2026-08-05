"""Playback Stage Worker executing immediate non-blocking audio playback."""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Tuple

from voicebridge.adapters import PlaybackAdapter
from voicebridge.config import Config
from voicebridge.pipeline.async_queue import BoundedAsyncQueue
from voicebridge.pipeline.contracts.schemas import LlmResponse, PlaybackRequest, PlaybackResponse, TtsResponse
from voicebridge.pipeline.events import EventType, PipelineEvent
from voicebridge.pipeline.workers.base_worker import BaseWorker


class PlaybackWorker(BaseWorker[Tuple[TtsResponse, LlmResponse], PlaybackResponse]):
    """Worker driving audio playback and emitting speech_ready events."""

    def __init__(
        self,
        config: Config,
        in_queue: BoundedAsyncQueue[Tuple[TtsResponse, LlmResponse]],
        stop_event: threading.Event,
        emit_event: Optional[Callable[[PipelineEvent], None]] = None,
        adapter: Optional[PlaybackAdapter] = None,
    ):
        super().__init__("Playback", config, in_queue=in_queue, out_queue=None, stop_event=stop_event)
        self.emit_event = emit_event
        self.adapter = adapter or PlaybackAdapter(config)

    def process_item(self, item: Tuple[TtsResponse, LlmResponse], wait_ms: float = 0.0) -> None:
        tts_resp, llm_resp = item

        req = PlaybackRequest(
            trace_id=tts_resp.trace_id,
            audio_path=tts_resp.audio_path,
            non_blocking=True,
        )
        self.adapter.play(req)

        if self.emit_event:
            self.emit_event(
                PipelineEvent(
                    type=EventType.SPEECH_READY,
                    direction=f"{llm_resp.source_language.upper()}->{llm_resp.target_language.upper()}",
                    speaker="speaker",
                    text=llm_resp.text,
                    translated_text=llm_resp.translated_text,
                    audio_url=tts_resp.audio_path,
                    latency_ms=tts_resp.inference_time_ms,
                    trace_id=tts_resp.trace_id,
                )
            )
