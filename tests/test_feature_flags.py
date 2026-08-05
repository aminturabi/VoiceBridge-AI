"""Unit tests for Feature Flags configuration evaluation."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from voicebridge.config import Config, load_config


def test_feature_flags_defaults(tmp_path: Path):
    cfg = Config({
        "feature_flags": {
            "enable_pipeline_contracts": True,
            "enable_new_interfaces": True,
            "enable_tracing": False,
        }
    })

    assert cfg.enable_pipeline_contracts is True
    assert cfg.enable_new_interfaces is True
    assert cfg.enable_tracing is False


def test_feature_flags_env_override(monkeypatch):
    cfg = Config({
        "feature_flags": {
            "enable_pipeline_contracts": True,
            "enable_tracing": False,
        }
    })

    monkeypatch.setenv("VOICEBRIDGE_ENABLE_PIPELINE_CONTRACTS", "false")
    monkeypatch.setenv("VOICEBRIDGE_ENABLE_TRACING", "true")

    assert cfg.enable_pipeline_contracts is False
    assert cfg.enable_tracing is True
