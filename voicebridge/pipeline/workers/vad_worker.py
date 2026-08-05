"""VAD Stage Worker producing speech segments to stt_queue."""

from __future__ import annotations

import threading
from typing import Any, Optional

import numpy as np

from voicebridge.adapters import VadAdapter
from voicebridge.config import Config
from voicebridge.pipeline.async_queue import BoundedAsyncQueue
from voicebridge.pipeline.contracts.schemas import VadRequest, VadResponse, generate_trace_id
from voicebridge.pipeline.workers.base_worker import BaseWorker


class VadWorker(BaseWorker[VadRequest, VadResponse]):
    """Worker reading PCM frames from audio source and detecting speech segments."""

    def __init__(
        self,
        config: Config,
        source: Any,
        out_queue: BoundedAsyncQueue[VadResponse],
        stop_event: threading.Event,
        adapter: Optional[VadAdapter] = None,
    ):
        super().__init__("VAD", config, in_queue=None, out_queue=out_queue, stop_event=stop_event)
        self.source = source
        self.adapter = adapter or VadAdapter(config)
        self.sample_rate = int(config.get("audio.sample_rate", 16000))

    def produce_step(self) -> None:
        if self.source is None:
            self.stop_event.set()
            return

        frame = self.source.read_frame()
        if frame is None or len(frame) == 0:
            return

        trace_id = generate_trace_id()
        audio_bytes = np.asarray(frame, dtype=np.float32).tobytes()
        req = VadRequest(trace_id=trace_id, audio_data=audio_bytes, sample_rate=self.sample_rate)

        resp = self.adapter.detect_speech(req)
        if resp.is_speech and self.out_queue:
            # Attach raw frame array to response payload for STT stage
            resp_data = (resp, frame)
            self.out_queue.put(resp_data)

    def process_item(self, item: VadRequest, wait_ms: float = 0.0) -> None:
        pass
