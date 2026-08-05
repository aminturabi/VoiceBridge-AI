"""Regression tests verifying Phase 1 compatibility when Phase 2 flags are disabled."""

from __future__ import annotations

import os
import pytest

from voicebridge.config import Config, load_config


def test_phase2_feature_flags_toggle():
    cfg = Config({
        "feature_flags": {
            "enable_streaming": False,
            "enable_async_pipeline": False,
            "enable_backpressure": False,
            "enable_model_warmup": False,
        }
    })

    assert cfg.enable_streaming is False
    assert cfg.enable_async_pipeline is False
    assert cfg.enable_backpressure is False
    assert cfg.enable_model_warmup is False


def test_phase2_env_var_overrides(monkeypatch):
    cfg = Config({})

    monkeypatch.setenv("VOICEBRIDGE_ENABLE_STREAMING", "false")
    monkeypatch.setenv("VOICEBRIDGE_ENABLE_ASYNC_PIPELINE", "true")
    monkeypatch.setenv("VOICEBRIDGE_ENABLE_BACKPRESSURE", "0")
    monkeypatch.setenv("VOICEBRIDGE_ENABLE_MODEL_WARMUP", "1")

    assert cfg.enable_streaming is False
    assert cfg.enable_async_pipeline is True
    assert cfg.enable_backpressure is False
    assert cfg.enable_model_warmup is True
