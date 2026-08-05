# VoiceBridge AI — Pipeline Contracts Specification

## Overview

All pipeline stages communicate via strongly typed contracts defined in `voicebridge.pipeline.contracts.schemas`. Every request and response contains a mandatory `trace_id` for end-to-end telemetry tracking.

---

## Contract Schemas

### 1. Input Capture

```python
class CaptureRequest(BaseModel):
    trace_id: str
    sample_rate: int = 16000
    channels: int = 1
    chunk_seconds: float = 4.0

class CaptureResponse(BaseModel):
    trace_id: str
    audio_data: bytes
    sample_rate: int
    duration_sec: float
    timestamp: float

class CaptureError(BaseModel):
    trace_id: str
    stage: str = "capture"
    error_message: str
    timestamp: float
```

### 2. Voice Activity Detection (VAD)

```python
class VadRequest(BaseModel):
    trace_id: str
    audio_bytes: bytes
    sample_rate: int = 16000
    min_speech_duration_ms: int = 400

class VadResponse(BaseModel):
    trace_id: str
    is_speech: bool
    confidence: float
    speech_duration_sec: float

class VadError(BaseModel):
    trace_id: str
    stage: str = "vad"
    error_message: str
    timestamp: float
```

### 3. Speech-To-Text (STT)

```python
class SttRequest(BaseModel):
    trace_id: str
    audio_source: str  # Path or memory buffer identifier
    source_language: str | None = None

class SttResponse(BaseModel):
    trace_id: str
    text: str
    detected_language: str
    confidence: float
    reliable_segments: int
    total_segments: int
    inference_time_ms: float

class SttErrorSchema(BaseModel):
    trace_id: str
    stage: str = "stt"
    error_message: str
    timestamp: float
```

### 4. LLM / Translation (LLM/NMT)

```python
class LlmRequest(BaseModel):
    trace_id: str
    text: str
    source_language: str
    target_language: str
    system_prompt: str | None = None

class LlmResponse(BaseModel):
    trace_id: str
    text: str
    translated_text: str
    source_language: str
    target_language: str
    inference_time_ms: float
    tokens_generated: int = 0

class LlmErrorSchema(BaseModel):
    trace_id: str
    stage: str = "llm"
    error_message: str
    timestamp: float
```

### 5. Text-To-Speech (TTS)

```python
class TtsRequest(BaseModel):
    trace_id: str
    text: str
    voice: str
    direction: str
    sentence_id: int

class TtsResponse(BaseModel):
    trace_id: str
    audio_path: str
    duration_sec: float
    inference_time_ms: float

class TtsErrorSchema(BaseModel):
    trace_id: str
    stage: str = "tts"
    error_message: str
    timestamp: float
```

### 6. Playback

```python
class PlaybackRequest(BaseModel):
    trace_id: str
    audio_path: str
    non_blocking: bool = True

class PlaybackResponse(BaseModel):
    trace_id: str
    success: bool
    played_duration_sec: float

class PlaybackError(BaseModel):
    trace_id: str
    stage: str = "playback"
    error_message: str
    timestamp: float
```
