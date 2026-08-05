"""Regression tests verifying Phase 1 & 2 compatibility when Phase 3 flags are disabled."""

from __future__ import annotations

import os
import pytest

from voicebridge.config import Config


def test_phase3_feature_flags_toggle():
    cfg = Config({
        "feature_flags": {
            "enable_intelligent_routing": False,
            "enable_fallback_chains": False,
            "enable_circuit_breaker": False,
            "enable_rate_limiting": False,
        }
    })

    assert cfg.enable_intelligent_routing is False
    assert cfg.enable_fallback_chains is False
    assert cfg.enable_circuit_breaker is False
    assert cfg.enable_rate_limiting is False


def test_phase3_env_var_overrides(monkeypatch):
    cfg = Config({})

    monkeypatch.setenv("VOICEBRIDGE_ENABLE_INTELLIGENT_ROUTING", "true")
    monkeypatch.setenv("VOICEBRIDGE_ENABLE_FALLBACK_CHAINS", "false")
    monkeypatch.setenv("VOICEBRIDGE_ENABLE_CIRCUIT_BREAKER", "1")
    monkeypatch.setenv("VOICEBRIDGE_ENABLE_RATE_LIMITING", "0")

    assert cfg.enable_intelligent_routing is True
    assert cfg.enable_fallback_chains is False
    assert cfg.enable_circuit_breaker is True
    assert cfg.enable_rate_limiting is False
