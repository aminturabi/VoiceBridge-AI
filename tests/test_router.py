"""Unit tests for ModelRouter quality tiers and provider ranking."""

from __future__ import annotations

import pytest

from voicebridge.config import Config
from voicebridge.routing.health_checker import ProviderHealthMonitor
from voicebridge.routing.quality_tiers import QualityTier
from voicebridge.routing.router import ModelRouter


@pytest.fixture
def router_config() -> Config:
    return Config({
        "routing": {
            "default_tier": "balanced",
            "latency_budget_ms": 1000.0,
        }
    })


def test_router_select_stt_provider(router_config: Config):
    router = ModelRouter(router_config)
    selected = router.select_stt_provider(language="en", quality_tier=QualityTier.FAST)
    assert selected in ("faster-whisper", "whisper-api", "vosk")


def test_router_select_llm_provider(router_config: Config):
    router = ModelRouter(router_config)
    selected = router.select_llm_provider(source_lang="en", target_lang="ar", quality_tier=QualityTier.BALANCED)
    assert selected in ("google", "argos", "nllb")


def test_router_ranks_healthy_provider_higher(router_config: Config):
    monitor = ProviderHealthMonitor.get_instance(router_config)
    monitor.record_latency("google", 50.0)
    monitor.record_latency("argos", 800.0)
    monitor.record_error("argos")

    router = ModelRouter(router_config, health_monitor=monitor)
    selected = router.select_llm_provider("en", "ar", quality_tier=QualityTier.FAST, available_providers=["argos", "google"])

    assert selected == "google"
