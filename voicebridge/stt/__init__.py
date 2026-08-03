"""STT package exports."""

from voicebridge.stt.base import SttBackend, SttError, Transcription
from voicebridge.stt.engine import SttEngine
from voicebridge.stt.faster_whisper_backend import FasterWhisperBackend
from voicebridge.stt.manager import SttManager
from voicebridge.stt.reliability import ReliabilityThresholds, segment_is_reliable

__all__ = [
    "SttBackend",
    "SttError",
    "Transcription",
    "SttEngine",
    "FasterWhisperBackend",
    "SttManager",
    "ReliabilityThresholds",
    "segment_is_reliable",
]
