"""Model Warm-up Manager for pre-loading engines and running warm-up inference."""

from __future__ import annotations

import time
import numpy as np

from voicebridge.adapters import LlmAdapter, SttAdapter, TtsAdapter, VadAdapter
from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.metrics.model_tracker import ModelLoadTracker
from voicebridge.pipeline.contracts.schemas import LlmRequest, SttRequest, TtsRequest, VadRequest, generate_trace_id

logger = get_logger(__name__)


class ModelWarmupManager:
    """Handles startup model pre-loading and warm-up inference to eliminate cold-start latency."""

    def __init__(self, config: Config):
        self._config = config
        self._tracker = ModelLoadTracker.get_instance()

    def warmup_all(self, source_lang: str = "en", target_lang: str = "ar") -> dict[str, float]:
        """Run warm-up inference for VAD, STT, LLM, and TTS if enabled by config."""
        if not self._config.enable_model_warmup:
            logger.info("Model warm-up disabled via configuration (lazy loading enabled).")
            return {}

        logger.info("Starting model warm-up phase...")
        durations = {}

        # 1. Warm-up VAD
        durations["vad"] = self._warmup_vad()

        # 2. Warm-up STT
        durations["stt"] = self._warmup_stt(source_lang)

        # 3. Warm-up LLM / Translation
        durations["llm"] = self._warmup_llm(source_lang, target_lang)

        # 4. Warm-up TTS
        durations["tts"] = self._warmup_tts(target_lang)

        logger.info("Model warm-up complete! Durations: %s", durations)
        return durations

    def _warmup_vad(self) -> float:
        t0 = time.perf_counter()
        try:
            adapter = VadAdapter(self._config)
            dummy_pcm = np.zeros(1600, dtype=np.float32).tobytes()
            req = VadRequest(trace_id=generate_trace_id(), audio_data=dummy_pcm)
            adapter.detect_speech(req)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._tracker.record_load("vad", adapter.name, load_time_ms=elapsed_ms)
            return elapsed_ms
        except Exception as err:
            logger.warning("VAD warm-up warning: %s", err)
            return (time.perf_counter() - t0) * 1000.0

    def _warmup_stt(self, source_lang: str) -> float:
        t0 = time.perf_counter()
        try:
            adapter = SttAdapter(self._config, label="warmup", source_lang=source_lang)
            dummy_pcm = np.zeros(16000, dtype=np.float32)
            req = SttRequest(trace_id=generate_trace_id(), audio_source=dummy_pcm, source_language=source_lang)
            adapter.transcribe(req)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._tracker.record_load("stt", adapter.name, load_time_ms=elapsed_ms)
            return elapsed_ms
        except Exception as err:
            logger.warning("STT warm-up warning: %s", err)
            return (time.perf_counter() - t0) * 1000.0

    def _warmup_llm(self, source_lang: str, target_lang: str) -> float:
        t0 = time.perf_counter()
        try:
            adapter = LlmAdapter(self._config)
            req = LlmRequest(
                trace_id=generate_trace_id(),
                text="Hello",
                source_language=source_lang,
                target_language=target_lang,
            )
            adapter.process_text(req)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._tracker.record_load("llm", adapter.name, load_time_ms=elapsed_ms)
            return elapsed_ms
        except Exception as err:
            logger.warning("LLM warm-up warning: %s", err)
            return (time.perf_counter() - t0) * 1000.0

    def _warmup_tts(self, target_lang: str) -> float:
        t0 = time.perf_counter()
        try:
            adapter = TtsAdapter(self._config)
            voice = self._config.language(target_lang)["edge_voice"]
            req = TtsRequest(
                trace_id=generate_trace_id(),
                text="Hello",
                voice=voice,
                direction=f"WARMUP->{target_lang.upper()}",
                sentence_id=0,
            )
            adapter.synthesize(req)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._tracker.record_load("tts", adapter.name, load_time_ms=elapsed_ms)
            return elapsed_ms
        except Exception as err:
            logger.warning("TTS warm-up warning: %s", err)
            return (time.perf_counter() - t0) * 1000.0
