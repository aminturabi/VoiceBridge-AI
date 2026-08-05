"""Unit tests for Pipeline Contracts and Schemas."""

from __future__ import annotations

import time
import pytest

from voicebridge.pipeline.contracts import (
    CaptureError,
    CaptureRequest,
    CaptureResponse,
    LlmErrorSchema,
    LlmRequest,
    LlmResponse,
    PlaybackError,
    PlaybackRequest,
    PlaybackResponse,
    SttErrorSchema,
    SttRequest,
    SttResponse,
    TtsErrorSchema,
    TtsRequest,
    TtsResponse,
    VadError,
    VadRequest,
    VadResponse,
    generate_trace_id,
)


def test_generate_trace_id():
    t1 = generate_trace_id()
    t2 = generate_trace_id()
    assert t1 != t2
    assert len(t1) == 36


def test_capture_contracts():
    req = CaptureRequest()
    assert req.sample_rate == 16000
    assert len(req.trace_id) == 36

    resp = CaptureResponse(trace_id=req.trace_id, audio_data=b"123", duration_sec=1.5)
    assert resp.trace_id == req.trace_id
    assert resp.audio_data == b"123"

    err = CaptureError(trace_id=req.trace_id, error_message="mic disconnect")
    assert err.stage == "capture"
    assert err.error_message == "mic disconnect"


def test_vad_contracts():
    req = VadRequest(trace_id="test-trace", audio_data=b"pcm_data")
    assert req.trace_id == "test-trace"

    resp = VadResponse(trace_id="test-trace", is_speech=True, confidence=0.98, speech_duration_sec=2.0)
    assert resp.is_speech is True
    assert resp.confidence == 0.98

    err = VadError(trace_id="test-trace", error_message="silero model crash")
    assert err.stage == "vad"


def test_stt_contracts():
    req = SttRequest(trace_id="stt-trace", audio_source="file.wav", source_language="en")
    assert req.audio_source == "file.wav"

    resp = SttResponse(trace_id="stt-trace", text="Hello world", detected_language="en", inference_time_ms=120.0)
    assert resp.text == "Hello world"
    assert resp.inference_time_ms == 120.0

    err = SttErrorSchema(trace_id="stt-trace", error_message="whisper failure")
    assert err.stage == "stt"


def test_llm_contracts():
    req = LlmRequest(trace_id="llm-trace", text="Hello", source_language="en", target_language="ar")
    assert req.target_language == "ar"

    resp = LlmResponse(
        trace_id="llm-trace", text="Hello", translated_text="مرحبا",
        source_language="en", target_language="ar", inference_time_ms=45.0, tokens_generated=1,
    )
    assert resp.translated_text == "مرحبا"
    assert resp.tokens_generated == 1

    err = LlmErrorSchema(trace_id="llm-trace", error_message="translation timeout")
    assert err.stage == "llm"


def test_tts_contracts():
    req = TtsRequest(trace_id="tts-trace", text="مرحبا", voice="ar-SA-ZariyahNeural")
    assert req.voice == "ar-SA-ZariyahNeural"

    resp = TtsResponse(trace_id="tts-trace", audio_path="/tmp/out.mp3", duration_sec=2.1, inference_time_ms=210.0)
    assert resp.audio_path == "/tmp/out.mp3"

    err = TtsErrorSchema(trace_id="tts-trace", error_message="edge-tts network issue")
    assert err.stage == "tts"


def test_playback_contracts():
    req = PlaybackRequest(trace_id="pb-trace", audio_path="/tmp/out.mp3")
    assert req.non_blocking is True

    resp = PlaybackResponse(trace_id="pb-trace", success=True, played_duration_sec=2.1)
    assert resp.success is True

    err = PlaybackError(trace_id="pb-trace", error_message="device occupied")
    assert err.stage == "playback"
