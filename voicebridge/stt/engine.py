"""faster-whisper wrapper.

Key design point vs. the prototype: each translation direction constructs its
OWN ``SttEngine`` (its own ``WhisperModel``). There is no shared model and no
global transcription lock, so the two directions of a two-way call transcribe
in parallel instead of serializing behind one lock.

Device selection walks ``stt.device_preference`` and falls back gracefully
(CUDA -> CPU) if a device fails to load.
"""

from __future__ import annotations

from dataclasses import dataclass

from faster_whisper import WhisperModel

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.stt.reliability import ReliabilityThresholds, segment_is_reliable

logger = get_logger(__name__)


@dataclass
class Transcription:
    """Result of transcribing one audio chunk."""

    text: str
    language: str
    reliable_segments: int
    total_segments: int


class SttEngine:
    """Owns a single WhisperModel and transcribes audio files/arrays."""

    def __init__(self, config: Config, label: str = "stt"):
        self._config = config
        self._label = label
        self._thresholds = ReliabilityThresholds.from_config(
            config.get("stt.reliability", {})
        )
        self._transcribe_opts = config.get("stt.transcribe", {})
        self.model, self.device, self.model_size = self._load_model()

    # -- loading ------------------------------------------------------------

    def _load_model(self) -> tuple[WhisperModel, str, str]:
        """Try each preferred device in order; return the first that loads."""
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
                import time
                from voicebridge.metrics.model_tracker import ModelLoadTracker

                logger.info(
                    "[%s] Loading Whisper %r on %s (%s)...",
                    self._label, model_size, device, compute_type,
                )
                start_t = time.perf_counter()
                model = WhisperModel(model_size, device=device, compute_type=compute_type)
                load_ms = (time.perf_counter() - start_t) * 1000.0

                ModelLoadTracker.get_instance().record_load(
                    component="stt",
                    name=f"whisper_{model_size}_{device}",
                    load_time_ms=load_ms,
                    device=device,
                    details={"compute_type": compute_type, "label": self._label},
                )
                logger.info("[%s] Whisper ready on %s (loaded in %.1fms)", self._label, device, load_ms)
                return model, device, model_size

            except Exception as error:  # noqa: BLE001 - want to try next device
                last_error = error
                logger.warning(
                    "[%s] Could not load on %s: %s", self._label, device, error
                )

        raise RuntimeError(
            f"[{self._label}] Failed to load Whisper on any device "
            f"({preference}). Last error: {last_error}"
        )

    # -- transcription ------------------------------------------------------

    def _raw_transcribe(self, audio_source):
        """Call model.transcribe with configured options, tolerating old versions."""
        opts = self._transcribe_opts
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
            )
        except TypeError:
            # Older faster-whisper may not accept every keyword above.
            logger.debug("[%s] Falling back to minimal transcribe kwargs", self._label)
            return self.model.transcribe(
                str(audio_source),
                vad_filter=opts.get("vad_filter", True),
                beam_size=opts.get("beam_size", 5),
                condition_on_previous_text=opts.get("condition_on_previous_text", False),
            )

    def transcribe(self, audio_source) -> Transcription:
        """Transcribe an audio file path (or np array) and filter by confidence.

        Applies the same reliability guards as the prototype. Cleaning/noise
        checks happen downstream in the buffer stage.
        """
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
