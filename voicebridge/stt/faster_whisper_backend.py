"""faster-whisper backend implementation."""

from __future__ import annotations

import time

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.stt.base import SttBackend, SttError, Transcription
from voicebridge.stt.reliability import ReliabilityThresholds, segment_is_reliable

logger = get_logger(__name__)


class FasterWhisperBackend(SttBackend):
    """STT backend powered by faster-whisper."""

    name: str = "faster-whisper"

    def __init__(self, config: Config, label: str = "stt", source_lang: str | None = None):
        self._config = config
        self._label = label
        self._source_lang = source_lang
        self._thresholds = ReliabilityThresholds.from_config(
            config.get("stt.reliability", {})
        )
        self._transcribe_opts = config.get("stt.transcribe", {})
        self.model = None
        self.device = None
        self.model_size = None
        self._loaded = False
        self._init_model()

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def _init_model(self) -> None:
        """Try each preferred device in order; load first that works."""
        if not self.is_available():
            logger.warning("[%s] faster-whisper package not installed", self._label)
            return

        preference = self._config.get("stt.device_preference", ["cpu"])
        last_error: Exception | None = None

        for device in preference:
            section = self._config.get(f"stt.{device}", None)
            if section is None:
                logger.warning("[%s] No config for device %r; skipping", self._label, device)
                continue

            model_size = section.get("model_size", "base")
            compute_type = section.get("compute_type", "int8")
            try:
                from faster_whisper import WhisperModel
                from voicebridge.metrics.model_tracker import ModelLoadTracker

                logger.info(
                    "[%s] Loading Whisper %r on %s (%s)...",
                    self._label, model_size, device, compute_type,
                )
                start_t = time.perf_counter()

                # Model path override support from config models.whisper_dir
                model_dir = self._config.path("models.whisper_dir", "models/whisper")
                model_name_or_path = model_size
                if (model_dir / model_size).exists():
                    model_name_or_path = str(model_dir / model_size)

                model = WhisperModel(model_name_or_path, device=device, compute_type=compute_type)
                load_ms = (time.perf_counter() - start_t) * 1000.0

                ModelLoadTracker.get_instance().record_load(
                    component="stt",
                    name=f"whisper_{model_size}_{device}",
                    load_time_ms=load_ms,
                    device=device,
                    details={"compute_type": compute_type, "label": self._label},
                )
                self.model = model
                self.device = device
                self.model_size = model_size
                self._loaded = True
                logger.info("[%s] Whisper ready on %s (loaded in %.1fms)", self._label, device, load_ms)
                return

            except Exception as error:  # noqa: BLE001
                last_error = error
                logger.warning(
                    "[%s] Could not load on %s: %s", self._label, device, error
                )

        logger.warning(
            "[%s] Failed to load Whisper on preferred devices (%s). Last error: %s",
            self._label, preference, last_error
        )

    def _raw_transcribe(self, audio_source):
        if not self._loaded or self.model is None:
            raise SttError(f"[{self._label}] FasterWhisper model is not loaded")

        opts = self._transcribe_opts
        kwargs = {}
        if self._source_lang:
            kwargs["language"] = self._source_lang

        try:
            return self.model.transcribe(
                str(audio_source),
                vad_filter=opts.get("vad_filter", True),
                vad_parameters={
                    "min_silence_duration_ms": opts.get(
                        "vad_min_silence_duration_ms", 500
                    )
                },
                beam_size=opts.get("beam_size", 5),
                temperature=opts.get("temperature", 0.0),
                condition_on_previous_text=opts.get("condition_on_previous_text", False),
                no_speech_threshold=opts.get("no_speech_threshold", 0.6),
                log_prob_threshold=opts.get("log_prob_threshold", -1.0),
                compression_ratio_threshold=opts.get("compression_ratio_threshold", 2.4),
                **kwargs,
            )
        except TypeError:
            return self.model.transcribe(
                str(audio_source),
                vad_filter=opts.get("vad_filter", True),
                beam_size=opts.get("beam_size", 5),
                condition_on_previous_text=opts.get("condition_on_previous_text", False),
                **kwargs,
            )

    def transcribe(self, audio_source) -> Transcription:
        from voicebridge.pipeline.text_utils import clean_text

        segments, info = self._raw_transcribe(audio_source)
        segment_list = list(segments)

        accepted: list[str] = []
        for segment in segment_list:
            segment_text = clean_text(getattr(segment, "text", ""))
            if segment_text and segment_is_reliable(segment, self._thresholds):
                accepted.append(segment_text)

        return Transcription(
            text=clean_text(" ".join(accepted)),
            language=getattr(info, "language", "unknown"),
            reliable_segments=len(accepted),
            total_segments=len(segment_list),
        )
