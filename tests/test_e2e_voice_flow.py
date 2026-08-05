"""Integration test for end-to-end voice flow pipeline execution."""

from unittest.mock import MagicMock
import pytest
from voicebridge.config import load_config
from voicebridge.pipeline.events import EventType
from voicebridge.pipeline.worker import DirectionWorker, DirectionSpec


def test_e2e_sentence_processing_flow(monkeypatch):
    """Test full processing flow from transcribed sentence through translation, TTS, and event publishing."""
    config = load_config()
    
    # Mock STT
    monkeypatch.setattr("voicebridge.pipeline.worker.SttManager", MagicMock())
    
    # Mocks for Translation, TTS, and LipSync
    mock_trans = MagicMock()
    mock_trans.translate.return_value = "Hello, how are you?"
    
    mock_tts = MagicMock()
    mock_tts.synthesize.return_value = "/tmp/fake_output.wav"
    
    mock_lipsync = MagicMock()
    mock_lipsync.generate.return_value = "/tmp/fake_synced.mp4"
    mock_lipsync.backend_name = "demo"
    
    published_events = []
    
    spec = DirectionSpec(source_lang="ar", target_lang="en", speaker="me")
    worker = DirectionWorker(
        config=config,
        spec=spec,
        source=None,
        translation=mock_trans,
        tts=mock_tts,
        lipsync=mock_lipsync,
        emit=published_events.append,
        stop_event=MagicMock(),
    )

    # Process simulated transcribed sentence
    worker._process_sentence("مرحبا كيف حالك")

    # Assert translation called
    mock_trans.translate.assert_called_once_with("مرحبا كيف حالك", "ar", "en")
    
    # Assert TTS called
    mock_tts.synthesize.assert_called_once()
    
    # Assert events emitted (SPEECH_READY)
    assert len(published_events) == 1
    event = published_events[0]
    assert event.type == EventType.SPEECH_READY
    assert event.speaker == "me"
    assert event.original_text == "مرحبا كيف حالك"
    assert event.translated_text == "Hello, how are you?"
    assert event.audio_url == "/tmp/fake_output.wav"
    assert event.video_url == "/tmp/fake_synced.mp4"
