"""Integration tests for AsyncPipelineOrchestrator and stage workers."""

from __future__ import annotations

import time
from unittest.mock import MagicMock
import pytest

from voicebridge.config import Config
from voicebridge.pipeline.async_pipeline import AsyncPipelineOrchestrator
from voicebridge.pipeline.contracts.schemas import LlmResponse, SttResponse, TtsResponse, VadResponse


@pytest.fixture
def test_config(tmp_path) -> Config:
    return Config({
        "app": {"output_dir": str(tmp_path / "output")},
        "feature_flags": {
            "enable_streaming": True,
            "enable_async_pipeline": True,
            "enable_backpressure": True,
        },
        "pipeline": {
            "queue_sizes": {
                "stt": 5,
                "llm": 5,
                "tts": 5,
                "playback": 10,
            }
        },
        "languages": {
            "en": {"display_name": "English", "edge_voice": "en-US-JennyNeural"},
            "ar": {"display_name": "Arabic", "edge_voice": "ar-SA-ZariyahNeural"},
        },
        "audio": {"sample_rate": 16000},
        "buffer": {
            "word_limit": 3,
            "timeout_seconds": 1.0,
            "sentence_endings": [".", "?"],
            "noise_phrases": [],
        },
    })


def test_async_pipeline_orchestrator_lifecycle(test_config: Config, monkeypatch):
    monkeypatch.setattr("voicebridge.adapters.stt_adapter.SttManager", MagicMock())
    mock_source = MagicMock()
    mock_source.read_frame.return_value = None

    orch = AsyncPipelineOrchestrator(
        config=test_config,
        source_lang="en",
        target_lang="ar",
        source=mock_source,
    )

    assert orch.is_running is False

    orch.start()
    assert orch.is_running is True

    status = orch.get_status()
    assert status["is_running"] is True
    assert "queues" in status
    assert "worker_utilization" in status

    orch.stop(timeout=1.0)
    assert orch.is_running is False
