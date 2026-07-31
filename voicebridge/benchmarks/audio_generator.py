"""Benchmark Audio Sample Generator.

Creates synthetic 16kHz PCM WAV audio files for benchmark testing:
- Short audio: 5 seconds
- Medium audio: 30 seconds
- Long audio: 120 seconds (2 minutes)
"""

from __future__ import annotations

import wave
from pathlib import Path
import numpy as np

from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)


def generate_benchmark_wav(
    output_path: Path,
    duration_sec: float = 5.0,
    sample_rate: int = 16000,
    frequency_hz: float = 440.0,
) -> Path:
    """Generates a mono 16-bit PCM WAV file of specified duration."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False)

    # Generate a modulated speech-like tone with brief pauses
    envelope = np.sin(2 * np.pi * 0.5 * t)  # 0.5 Hz modulation
    audio_signal = 0.5 * np.sin(2 * np.pi * frequency_hz * t) * envelope

    # Convert to 16-bit signed PCM
    pcm_data = (audio_signal * 32767).astype(np.int16)

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)        # Mono
        wav_file.setsampwidth(2)       # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data.tobytes())

    logger.info("Generated benchmark WAV: %s (%.1fs)", output_path.name, duration_sec)
    return output_path
