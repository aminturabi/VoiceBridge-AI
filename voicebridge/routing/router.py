"""Intelligent Model Router selecting optimal providers based on quality tiers, latency budgets, and health scores."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.routing.health_checker import ProviderHealthMonitor
from voicebridge.routing.quality_tiers import QUALITY_LATENCY_BUDGETS_MS, QualityTier

logger = get_logger(__name__)


class ModelRouter:
    """Centralized Intelligent Model Router."""

    def __init__(self, config: Config, health_monitor: Optional[ProviderHealthMonitor] = None):
        self.config = config
        self.health_monitor = health_monitor or ProviderHealthMonitor.get_instance(config)
        self.default_tier = QualityTier(config.get("routing.default_tier", "balanced"))
        self.latency_budget_ms = float(config.get("routing.latency_budget_ms", 1500.0))

    def select_stt_provider(
        self,
        language: str = "en",
        quality_tier: Optional[QualityTier] = None,
        available_providers: Optional[List[str]] = None,
    ) -> str:
        """Select optimal STT provider."""
        candidates = available_providers or ["faster-whisper", "whisper-api", "vosk"]
        return self._rank_providers("stt", candidates, quality_tier or self.default_tier)

    def select_llm_provider(
        self,
        source_lang: str,
        target_lang: str,
        quality_tier: Optional[QualityTier] = None,
        available_providers: Optional[List[str]] = None,
    ) -> str:
        """Select optimal LLM / Translation provider."""
        candidates = available_providers or ["google", "argos", "nllb"]
        return self._rank_providers("llm", candidates, quality_tier or self.default_tier)

    def select_tts_provider(
        self,
        language: str = "en",
        quality_tier: Optional[QualityTier] = None,
        available_providers: Optional[List[str]] = None,
    ) -> str:
        """Select optimal TTS provider."""
        candidates = available_providers or ["edge-tts", "coqui"]
        return self._rank_providers("tts", candidates, quality_tier or self.default_tier)

    def _rank_providers(self, modality: str, candidates: List[str], tier: QualityTier) -> str:
        if not candidates:
            raise ValueError(f"No candidates registered for modality {modality}")

        budget = QUALITY_LATENCY_BUDGETS_MS.get(tier, self.latency_budget_ms)

        scored: List[tuple[float, str]] = []
        for p in candidates:
            health = self.health_monitor.get_health_score(p)
            avg_lat = self.health_monitor.provider_latencies_ms.get(p, 100.0)

            # Score formula: health score (0..1) minus latency penalty if over budget
            lat_penalty = max(0.0, (avg_lat - budget) / budget) * 0.5
            total_score = health - lat_penalty

            scored.append((total_score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        winner = scored[0][1]

        logger.info(
            "[ModelRouter] Selected %s provider '%s' (Tier=%s, Score=%.2f)",
            modality.upper(), winner, tier.value, scored[0][0]
        )
        return winner
