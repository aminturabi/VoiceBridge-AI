"""TTS Stage Worker synthesizing speech audio from translated text chunks."""

from __future__ import annotations

import threading
from typing import Optional

from voicebridge.adapters import TtsAdapter
from voicebridge.config import Config
from voicebridge.pipeline.async_queue import BoundedAsyncQueue
from voicebridge.pipeline.contracts.schemas import LlmResponse, TtsRequest, TtsResponse
from voicebridge.pipeline.workers.base_worker import BaseWorker


class TtsWorker(BaseWorker[LlmResponse, TtsResponse]):
    """Worker handling text-to-speech synthesis."""

    def __init__(
        self,
        config: Config,
        target_lang: str,
        in_queue: BoundedAsyncQueue[LlmResponse],
        out_queue: BoundedAsyncQueue[TtsResponse],
        stop_event: threading.Event,
        adapter: Optional[TtsAdapter] = None,
    ):
        super().__init__("TTS", config, in_queue=in_queue, out_queue=out_queue, stop_event=stop_event)
        self.target_lang = target_lang
        self.voice = config.language(target_lang)["edge_voice"]
        self.sentence_counter = 0
        self.adapter = adapter or TtsAdapter(config)

    def process_item(self, item: LlmResponse, wait_ms: float = 0.0) -> None:
        self.sentence_counter += 1
        req = TtsRequest(
            trace_id=item.trace_id,
            text=item.translated_text,
            voice=self.voice,
            direction=f"{item.source_language.upper()}->{item.target_language.upper()}",
            sentence_id=self.sentence_counter,
        )
        tts_resp = self.adapter.synthesize(req)

        if tts_resp.audio_path and self.out_queue:
            # Pass (tts_resp, llm_resp) tuple to playback stage
            self.out_queue.put((tts_resp, item))
