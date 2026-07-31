"""Audio playback.

Replaces the prototype's blocking ``playsound``. edge-tts emits MP3, so we
decode to raw PCM with ffmpeg (already on PATH) and play through sounddevice.

``non_blocking=True`` returns immediately after starting playback, letting the
TTS worker generate the next clip while the current one plays. A per-player
lock still serializes the actual audio device so clips don't overlap.
"""

from __future__ import annotations

import subprocess
import threading

import numpy as np
import sounddevice as sd

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


class AudioPlayer:
    """Decode + play audio files, blocking or non-blocking."""

    def __init__(self, config: Config):
        self._non_blocking = bool(config.get("audio.playback.non_blocking", True))
        self._device_lock = threading.Lock()

    def _decode(self, path: str, sample_rate: int = 24000) -> np.ndarray:
        """Decode any audio file to mono float32 PCM via ffmpeg."""
        cmd = [
            "ffmpeg", "-nostdin", "-loglevel", "error",
            "-i", str(path),
            "-f", "f32le", "-acodec", "pcm_f32le",
            "-ac", "1", "-ar", str(sample_rate), "pipe:1",
        ]
        result = subprocess.run(cmd, capture_output=True, check=True)
        return np.frombuffer(result.stdout, dtype=np.float32)

    def _play_blocking(self, path: str) -> None:
        sample_rate = 24000
        try:
            pcm = self._decode(path, sample_rate)
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            logger.error("Could not decode %s: %s", path, error)
            return
        with self._device_lock:
            sd.play(pcm, samplerate=sample_rate)
            sd.wait()

    def play(self, path: str) -> threading.Thread | None:
        """Play an audio file. Non-blocking returns the playback thread."""
        if self._non_blocking:
            thread = threading.Thread(
                target=self._play_blocking, args=(path,), daemon=True,
                name="AudioPlayback",
            )
            thread.start()
            return thread
        self._play_blocking(path)
        return None

    def stop(self) -> None:
        try:
            sd.stop()
        except Exception:  # noqa: BLE001
            pass
