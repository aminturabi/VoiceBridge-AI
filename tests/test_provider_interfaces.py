"""Unit tests for Provider Interfaces and Adapters."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from voicebridge.adapters import LlmAdapter, PlaybackAdapter, SttAdapter, TtsAdapter, VadAdapter
from voicebridge.models import BaseLLM, BasePlayback, BaseSTT, BaseTTS, BaseVAD
from voicebridge.pipeline.contracts import LlmRequest, PlaybackRequest, SttRequest, TtsRequest, VadRequest
from voicebridge.stt.base import Transcription


def test_stt_adapter_implements_base_stt():
    mock_manager = MagicMock()
    mock_manager.backend_name = "mock_whisper"
    mock_manager.transcribe.return_value = Transcription(
        text="Testing STT adapter", language="en", reliable_segments=1, total_segments=1
    )

    adapter = SttAdapter(config=MagicMock(), manager=mock_manager)
    assert isinstance(adapter, BaseSTT)
    assert adapter.is_available() is True

    req = SttRequest(trace_id="t-stt", audio_source="dummy.wav", source_language="en")
    resp = adapter.transcribe(req)

    assert resp.trace_id == "t-stt"
    assert resp.text == "Testing STT adapter"
    assert resp.detected_language == "en"
    assert resp.confidence == 1.0


def test_llm_adapter_implements_base_llm():
    mock_manager = MagicMock()
    mock_manager.backend_names = ["google", "argos"]
    mock_manager.translate.return_value = "مرحبا بالعالم"

    adapter = LlmAdapter(config=MagicMock(), manager=mock_manager)
    assert isinstance(adapter, BaseLLM)
    assert adapter.is_available() is True

    req = LlmRequest(trace_id="t-llm", text="Hello world", source_language="en", target_language="ar")
    resp = adapter.process_text(req)

    assert resp.trace_id == "t-llm"
    assert resp.translated_text == "مرحبا بالعالم"
    assert resp.tokens_generated == 2


def test_tts_adapter_implements_base_tts():
    mock_manager = MagicMock()
    mock_manager.backend_name = "edge-tts"
    mock_manager.synthesize.return_value = "/tmp/generated.mp3"

    adapter = TtsAdapter(config=MagicMock(), manager=mock_manager)
    assert isinstance(adapter, BaseTTS)
    assert adapter.is_available() is True

    req = TtsRequest(trace_id="t-tts", text="Welcome", voice="en-US-JennyNeural")
    resp = adapter.synthesize(req)

    assert resp.trace_id == "t-tts"
    assert resp.audio_path == "/tmp/generated.mp3"


def test_vad_adapter_implements_base_vad():
    mock_segmenter = MagicMock()
    mock_segmenter.add_frame.return_value = [b"speech_data_chunk"]

    adapter = VadAdapter(config=MagicMock(), segmenter=mock_segmenter)
    assert isinstance(adapter, BaseVAD)
    assert adapter.is_available() is True

    req = VadRequest(trace_id="t-vad", audio_data=b"0" * 3200, sample_rate=16000)
    resp = adapter.detect_speech(req)

    assert resp.trace_id == "t-vad"
    assert resp.is_speech is True


def test_playback_adapter_implements_base_playback():
    mock_player = MagicMock()

    adapter = PlaybackAdapter(config=MagicMock(), player=mock_player)
    assert isinstance(adapter, BasePlayback)

    req = PlaybackRequest(trace_id="t-pb", audio_path="/tmp/test.mp3")
    resp = adapter.play(req)

    assert resp.trace_id == "t-pb"
    assert resp.success is True
    mock_player.play.assert_called_once_with("/tmp/test.mp3")

    adapter.stop()
    mock_player.stop.assert_called_once()
