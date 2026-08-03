"""TTS package exports."""

from voicebridge.tts.base import TtsBackend, TtsError
from voicebridge.tts.coqui_backend import CoquiBackend
from voicebridge.tts.edge_tts_backend import EdgeTtsBackend
from voicebridge.tts.engine import TtsEngine
from voicebridge.tts.manager import TtsManager

__all__ = [
    "TtsBackend",
    "TtsError",
    "EdgeTtsBackend",
    "CoquiBackend",
    "TtsEngine",
    "TtsManager",
]
