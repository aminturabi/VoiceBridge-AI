"""Quality Tiers and Latency Budget constants for Intelligent Model Routing."""

from __future__ import annotations

import enum


class QualityTier(str, enum.Enum):
    FAST = "fast"                # Lowest latency (e.g., tiny models, online fast APIs)
    BALANCED = "balanced"        # Optimal balance of speed and quality (default)
    HIGH_QUALITY = "high_quality"# Maximum output quality (e.g., large models)


QUALITY_LATENCY_BUDGETS_MS = {
    QualityTier.FAST: 400.0,
    QualityTier.BALANCED: 1200.0,
    QualityTier.HIGH_QUALITY: 3000.0,
}
