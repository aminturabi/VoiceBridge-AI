"""Audio capture sources and chunk persistence.

Two producers, matching the prototype's two pipelines but cleaned up:

* :class:`MicrophoneSource` streams mic frames through a :class:`VadSegmenter`
  and yields utterance-sized numpy segments (dynamic chunking).
* :class:`WavFileSource` yields a single segment from a WAV file (placeholder
  for the future Chrome tab-audio extension).

``save_segment_wav`` writes a float32 segment to an int16 PCM WAV that
faster-whisper can read.
"""

from __future__ import annotations

import queue
import threading
import uuid
from pathlib import Path
from typing import Iterator

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import read as wav_read
from scipy.io.wavfile import write as wav_write

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.audio.vad import VadSegmenter

logger = get_logger(__name__)


def save_segment_wav(segment: np.ndarray, sample_rate: int, dest_dir: Path, tag: str) -> Path:
    """Write a float32 [-1,1] segment as int16 PCM WAV; return the path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    audio_file = dest_dir / f"{tag}_{uuid.uuid4().hex}.wav"
    pcm = np.clip(segment, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)
    wav_write(str(audio_file), sample_rate, pcm)
    return audio_file


class MicrophoneSource:
    """Stream mic audio and yield VAD-delimited segments until stopped."""

    def __init__(self, config: Config, stop_event: threading.Event):
        self._sample_rate = int(config.get("audio.sample_rate", 16000))
        self._channels = int(config.get("audio.channels", 1))
        self._vad_enabled = bool(config.get("audio.vad.enabled", True))
        self._chunk_seconds = float(config.get("audio.chunk_seconds", 4))
        self._stop_event = stop_event
        self._segmenter = VadSegmenter(config) if self._vad_enabled else None
        # Frames arriving from the sounddevice callback thread.
        self._frame_queue: "queue.Queue[np.ndarray | None]" = queue.Queue()

    def _callback(self, indata, frames, time_info, status):  # noqa: ANN001
        if status:
            logger.debug("Mic status: %s", status)
        self._frame_queue.put(indata[:, 0].copy())

    def segments(self) -> Iterator[np.ndarray]:
        """Yield audio segments. Blocks until stop_event is set."""
        if self._vad_enabled:
            yield from self._vad_segments()
        else:
            yield from self._fixed_segments()

    def _vad_segments(self) -> Iterator[np.ndarray]:
        blocksize = int(self._sample_rate * 0.1)  # 100ms frames
        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="float32",
            blocksize=blocksize,
            callback=self._callback,
        ):
            logger.info("Microphone open (VAD chunking)")
            while not self._stop_event.is_set():
                try:
                    frame = self._frame_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                if frame is None:
                    break
                for segment in self._segmenter.add_frame(frame):
                    yield segment
            for segment in self._segmenter.flush():
                yield segment
        logger.info("Microphone closed")

    def _fixed_segments(self) -> Iterator[np.ndarray]:
        """Legacy fixed-length chunking (VAD disabled)."""
        frames = int(self._chunk_seconds * self._sample_rate)
        logger.info("Microphone open (fixed %.1fs chunks)", self._chunk_seconds)
        while not self._stop_event.is_set():
            recording = sd.rec(
                frames, samplerate=self._sample_rate, channels=self._channels,
                dtype="float32",
            )
            sd.wait()
            if self._stop_event.is_set():
                break
            yield recording[:, 0].copy()
        logger.info("Microphone closed")


class WavFileSource:
    """Yield a single segment from a WAV file (Pipeline B placeholder)."""

    def __init__(self, config: Config, wav_path: Path):
        self._sample_rate = int(config.get("audio.sample_rate", 16000))
        self._wav_path = Path(wav_path)

    def segments(self) -> Iterator[np.ndarray]:
        sr, data = wav_read(str(self._wav_path))
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32767.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483647.0
        else:
            data = data.astype(np.float32)
        if data.ndim > 1:
            data = data.mean(axis=1)
        logger.info("Loaded WAV %s (%d Hz, %d samples)", self._wav_path.name, sr, len(data))
        yield data
