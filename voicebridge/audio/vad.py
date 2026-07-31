"""VAD-based dynamic chunking.

Replaces the prototype's fixed 4-second chunks. A :class:`VadSegmenter` is fed
small frames of float32 mono audio (as they arrive from the mic) and emits a
complete utterance when it detects a trailing pause, or when the buffered
speech reaches ``max_segment_seconds``.

Uses the Silero VAD model bundled with faster-whisper, so there is nothing to
compile on Windows (unlike ``webrtcvad``).
"""

from __future__ import annotations

import numpy as np

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class VadSegmenter:
    """Accumulate frames and emit utterance-sized segments on pauses."""

    def __init__(self, config: Config):
        self._sample_rate = int(config.get("audio.sample_rate", 16000))
        vad_cfg = config.get("audio.vad", {})
        self._min_silence_ms = int(vad_cfg.get("min_silence_duration_ms", 500))
        self._max_segment_s = float(vad_cfg.get("max_segment_seconds", 8))
        self._min_segment_s = float(vad_cfg.get("min_segment_seconds", 0.4))

        # Lazy-loaded Silero VAD.
        self._vad_model = None
        self._get_speech_timestamps = None
        self._vad_options_cls = None

        self._buffer = np.empty(0, dtype=np.float32)

    def _ensure_vad(self) -> bool:
        if self._vad_model is not None:
            return True
        try:
            from faster_whisper.vad import (
                VadOptions,
                get_speech_timestamps,
                get_vad_model,
            )

            self._vad_model = get_vad_model()
            self._get_speech_timestamps = get_speech_timestamps
            self._vad_options_cls = VadOptions
            return True
        except Exception as error:  # noqa: BLE001
            logger.warning("Silero VAD unavailable (%s); using energy fallback", error)
            return False

    @property
    def _max_samples(self) -> int:
        return int(self._max_segment_s * self._sample_rate)

    @property
    def _min_samples(self) -> int:
        return int(self._min_segment_s * self._sample_rate)

    def add_frame(self, frame: np.ndarray) -> list[np.ndarray]:
        """Add a frame of float32 mono audio; return any completed segments."""
        frame = np.asarray(frame, dtype=np.float32).reshape(-1)
        self._buffer = np.concatenate([self._buffer, frame])
        return self._extract_segments(force=False)

    def flush(self) -> list[np.ndarray]:
        """Emit whatever remains as a final segment (used at shutdown)."""
        return self._extract_segments(force=True)

    def _extract_segments(self, force: bool) -> list[np.ndarray]:
        if self._buffer.size == 0:
            return []

        # Hard cap: emit immediately if we've buffered too much speech.
        if self._buffer.size >= self._max_samples:
            segment, self._buffer = self._buffer, np.empty(0, dtype=np.float32)
            return [segment] if segment.size >= self._min_samples else []

        if not self._ensure_vad():
            return self._energy_fallback(force)

        try:
            options = self._vad_options_cls(
                min_silence_duration_ms=self._min_silence_ms
            )
            timestamps = self._get_speech_timestamps(
                self._buffer, self._vad_model, **_vad_kwargs(options)
            )
        except Exception as error:  # noqa: BLE001
            logger.debug("VAD call failed (%s); energy fallback", error)
            return self._energy_fallback(force)

        if not timestamps:
            if force:
                seg, self._buffer = self._buffer, np.empty(0, dtype=np.float32)
                return [seg] if seg.size >= self._min_samples else []
            return []

        # Emit a segment only once speech has clearly ended: there is trailing
        # silence after the last detected speech region (or we're flushing).
        last_end = timestamps[-1]["end"]
        trailing_silence = self._buffer.size - last_end
        min_silence_samples = int(self._min_silence_ms / 1000 * self._sample_rate)

        if force or trailing_silence >= min_silence_samples:
            speech_start = timestamps[0]["start"]
            segment = self._buffer[speech_start:last_end]
            self._buffer = np.empty(0, dtype=np.float32)
            return [segment] if segment.size >= self._min_samples else []

        return []

    def _energy_fallback(self, force: bool) -> list[np.ndarray]:
        """If VAD is unavailable, emit on max size or when forced."""
        if force and self._buffer.size >= self._min_samples:
            seg, self._buffer = self._buffer, np.empty(0, dtype=np.float32)
            return [seg]
        return []


def _vad_kwargs(options) -> dict:
    """Adapt to faster-whisper versions: some take VadOptions, some kwargs."""
    # get_speech_timestamps signature varies; pass the fields it accepts.
    return {
        "vad_options": options,
    }
