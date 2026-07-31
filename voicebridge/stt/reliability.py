"""Confidence-based filtering of Whisper segments.

Kept separate and pure so it can be unit tested with lightweight stand-in
objects (any object exposing the three probability attributes works).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReliabilityThresholds:
    """Cut-offs used to drop likely silence hallucinations."""

    max_no_speech_prob: float = 0.85
    min_avg_logprob: float = -1.5
    max_compression_ratio: float = 2.8

    @classmethod
    def from_config(cls, cfg_section: dict) -> "ReliabilityThresholds":
        return cls(
            max_no_speech_prob=cfg_section.get("max_no_speech_prob", 0.85),
            min_avg_logprob=cfg_section.get("min_avg_logprob", -1.5),
            max_compression_ratio=cfg_section.get("max_compression_ratio", 2.8),
        )


def segment_is_reliable(segment, thresholds: ReliabilityThresholds) -> bool:
    """Use Whisper confidence fields to reduce silence hallucinations.

    ``segment`` is any object exposing ``no_speech_prob``, ``avg_logprob`` and
    ``compression_ratio`` (a faster-whisper Segment, or a test stub).
    """
    no_speech_prob = getattr(segment, "no_speech_prob", 0.0) or 0.0
    avg_logprob = getattr(segment, "avg_logprob", 0.0) or 0.0
    compression_ratio = getattr(segment, "compression_ratio", 0.0) or 0.0

    if no_speech_prob > thresholds.max_no_speech_prob:
        return False
    if avg_logprob < thresholds.min_avg_logprob:
        return False
    if compression_ratio > thresholds.max_compression_ratio:
        return False

    return True
