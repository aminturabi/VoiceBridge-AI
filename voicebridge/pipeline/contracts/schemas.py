"""Strongly typed pipeline request, response, and error schemas.

Every stage contract carries a mandatory trace_id for end-to-end telemetry.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


def generate_trace_id() -> str:
    """Generate a unique trace ID."""
    return str(uuid.uuid4())


# --- 1. Input Capture Contracts ---

@dataclass
class CaptureRequest:
    trace_id: str = field(default_factory=generate_trace_id)
    sample_rate: int = 16000
    channels: int = 1
    chunk_seconds: float = 4.0
    source_kind: str = "microphone"
    wav_path: Optional[str] = None


@dataclass
class CaptureResponse:
    trace_id: str
    audio_data: bytes
    sample_rate: int = 16000
    duration_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class CaptureError:
    trace_id: str
    stage: str = "capture"
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)


# --- 2. VAD Contracts ---

@dataclass
class VadRequest:
    trace_id: str
    audio_data: bytes
    sample_rate: int = 16000
    min_speech_duration_ms: int = 400


@dataclass
class VadResponse:
    trace_id: str
    is_speech: bool
    confidence: float
    speech_duration_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class VadError:
    trace_id: str
    stage: str = "vad"
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)


# --- 3. Speech-To-Text (STT) Contracts ---

@dataclass
class SttRequest:
    trace_id: str
    audio_source: Any  # File path or audio array
    source_language: Optional[str] = None


@dataclass
class SttResponse:
    trace_id: str
    text: str
    detected_language: str = "en"
    confidence: float = 1.0
    reliable_segments: int = 0
    total_segments: int = 0
    inference_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class SttErrorSchema:
    trace_id: str
    stage: str = "stt"
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)


# --- 4. LLM / Translation Contracts ---

@dataclass
class LlmRequest:
    trace_id: str
    text: str
    source_language: str
    target_language: str
    system_prompt: Optional[str] = None


@dataclass
class LlmResponse:
    trace_id: str
    text: str
    translated_text: str
    source_language: str
    target_language: str
    inference_time_ms: float = 0.0
    tokens_generated: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class LlmErrorSchema:
    trace_id: str
    stage: str = "llm"
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)


# --- 5. Text-To-Speech (TTS) Contracts ---

@dataclass
class TtsRequest:
    trace_id: str
    text: str
    voice: str
    direction: str = "EN->AR"
    sentence_id: int = 0


@dataclass
class TtsResponse:
    trace_id: str
    audio_path: str
    duration_sec: float = 0.0
    inference_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class TtsErrorSchema:
    trace_id: str
    stage: str = "tts"
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)


# --- 6. Playback Contracts ---

@dataclass
class PlaybackRequest:
    trace_id: str
    audio_path: str
    non_blocking: bool = True


@dataclass
class PlaybackResponse:
    trace_id: str
    success: bool = True
    played_duration_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class PlaybackError:
    trace_id: str
    stage: str = "playback"
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)
