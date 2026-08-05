"""Unit tests for ModelWarmupManager startup preloading."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from voicebridge.config import Config
from voicebridge.warmup import ModelWarmupManager


def test_model_warmup_disabled():
    cfg = Config({"feature_flags": {"enable_model_warmup": False}})
    mgr = ModelWarmupManager(cfg)
    results = mgr.warmup_all()
    assert results == {}


@patch("voicebridge.warmup.VadAdapter")
@patch("voicebridge.warmup.SttAdapter")
@patch("voicebridge.warmup.LlmAdapter")
@patch("voicebridge.warmup.TtsAdapter")
def test_model_warmup_enabled(mock_tts, mock_llm, mock_stt, mock_vad):
    cfg = Config({
        "feature_flags": {"enable_model_warmup": True},
        "languages": {"ar": {"edge_voice": "ar-SA-ZariyahNeural"}},
        "app": {"output_dir": "temp_speech"},
    })

    mgr = ModelWarmupManager(cfg)
    results = mgr.warmup_all("en", "ar")

    assert "vad" in results
    assert "stt" in results
    assert "llm" in results
    assert "tts" in results

    mock_vad.assert_called_once()
    mock_stt.assert_called_once()
    mock_llm.assert_called_once()
    mock_tts.assert_called_once()
