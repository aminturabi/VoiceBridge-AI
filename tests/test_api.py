"""API smoke tests: app wiring, info endpoint, media URL rewriting, broker.

These avoid loading real STT models or touching audio devices; they exercise
the FastAPI surface and the thread->async event broker in isolation.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from voicebridge.api.app import _with_media_urls, create_app
from voicebridge.api.broker import EventBroker
from voicebridge.pipeline.events import EventType, PipelineEvent


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def test_info_endpoint(client):
    res = client.get("/api/info")
    assert res.status_code == 200
    data = res.json()
    assert "languages" in data
    assert "en" in data["languages"]
    assert data["pipeline"]["running"] is False


def test_index_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "VoiceBridge" in res.text


def test_stop_when_not_running(client):
    res = client.post("/api/stop")
    assert res.status_code == 200
    assert res.json()["status"] == "not running"


def test_media_url_rewrite():
    def media(path):
        # Simulate the closure: only paths under output dir get URLs.
        return "/media/x.mp3" if path.endswith(".mp3") else ""

    payload = {"audio_url": "/abs/out/x.mp3", "video_url": "/abs/face.mp4"}
    out = _with_media_urls(payload, media)
    assert out["audio_url"] == "/media/x.mp3"
    assert out["video_url"] == ""


def test_broker_history_without_loop():
    broker = EventBroker()
    event = PipelineEvent(type=EventType.TRANSCRIPT, direction="EN->AR", speaker="me", text="hi")
    broker.publish(event)  # no loop bound yet -> goes to history
    assert len(broker.history) == 1
    assert broker.history[0]["text"] == "hi"


def test_broker_delivers_to_subscriber():
    async def scenario():
        broker = EventBroker()
        broker.bind_loop(asyncio.get_running_loop())
        queue_ = await broker.subscribe()
        event = PipelineEvent(type=EventType.TRANSLATION, direction="AR->EN",
                              speaker="other", text="مرحبا", translated_text="hello")
        broker.publish(event)
        payload = await asyncio.wait_for(queue_.get(), timeout=2)
        assert payload["translated_text"] == "hello"
        broker.unsubscribe(queue_)

    asyncio.run(scenario())


def test_worker_speaker_other_text_only(monkeypatch):
    """Verify that speaker 'other' emits translation event but skips TTS synthesis."""
    from unittest.mock import MagicMock
    from voicebridge.pipeline.worker import DirectionWorker, DirectionSpec
    from voicebridge.config import load_config

    config = load_config()
    monkeypatch.setattr("voicebridge.pipeline.worker.SttManager", MagicMock())
    spec = DirectionSpec(source_lang="ar", target_lang="en", speaker="other")
    mock_trans = MagicMock()
    mock_trans.translate.return_value = "hello"
    mock_tts = MagicMock()
    events = []

    worker = DirectionWorker(
        config=config,
        spec=spec,
        source=None,
        translation=mock_trans,
        tts=mock_tts,
        lipsync=MagicMock(),
        emit=events.append,
        stop_event=MagicMock(),
    )

    worker._process_sentence("مرحبا")

    # Should emit TRANSLATION event
    assert len(events) == 1
    assert events[0].type == EventType.TRANSLATION
    assert events[0].translated_text == "hello"
    # TTS synthesize should not have been called for speaker 'other'
    mock_tts.synthesize.assert_not_called()

