"""VAD Provider Adapter insulating core logic from Silero/VAD specifics."""

from __future__ import annotations

import numpy as np

from voicebridge.audio.vad import VadSegmenter
from voicebridge.config import Config
from voicebridge.models.vad import BaseVAD
from voicebridge.pipeline.contracts.schemas import VadRequest, VadResponse


class VadAdapter(BaseVAD):
    """Adapter wrapping VadSegmenter into the BaseVAD interface."""

    def __init__(self, config: Config, segmenter: VadSegmenter | None = None):
        self._config = config
        self._segmenter = segmenter or VadSegmenter(config)
        self.name = "adapter_silero_vad"

    def is_available(self) -> bool:
        return True

    def detect_speech(self, request: VadRequest) -> VadResponse:
        audio_arr = np.frombuffer(request.audio_data, dtype=np.float32)
        segments = self._segmenter.add_frame(audio_arr)
        has_speech = len(segments) > 0
        dur_sec = sum(len(s) for s in segments) / float(request.sample_rate) if has_speech else 0.0

        return VadResponse(
            trace_id=request.trace_id,
            is_speech=has_speech,
            confidence=1.0 if has_speech else 0.0,
            speech_duration_sec=dur_sec,
        )
