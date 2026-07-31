"""Unit tests for STT segment reliability filtering."""

from dataclasses import dataclass

from voicebridge.stt.reliability import ReliabilityThresholds, segment_is_reliable


@dataclass
class FakeSegment:
    """Minimal stand-in for a faster-whisper Segment."""

    no_speech_prob: float = 0.0
    avg_logprob: float = 0.0
    compression_ratio: float = 1.0


THRESHOLDS = ReliabilityThresholds()


def test_clean_segment_is_reliable():
    seg = FakeSegment(no_speech_prob=0.1, avg_logprob=-0.3, compression_ratio=1.5)
    assert segment_is_reliable(seg, THRESHOLDS) is True


def test_high_no_speech_prob_rejected():
    seg = FakeSegment(no_speech_prob=0.95)
    assert segment_is_reliable(seg, THRESHOLDS) is False


def test_low_logprob_rejected():
    seg = FakeSegment(avg_logprob=-2.0)
    assert segment_is_reliable(seg, THRESHOLDS) is False


def test_high_compression_ratio_rejected():
    seg = FakeSegment(compression_ratio=3.5)
    assert segment_is_reliable(seg, THRESHOLDS) is False


def test_boundary_values_are_reliable():
    # Exactly at the thresholds should pass (strict comparisons).
    seg = FakeSegment(
        no_speech_prob=0.85, avg_logprob=-1.5, compression_ratio=2.8
    )
    assert segment_is_reliable(seg, THRESHOLDS) is True


def test_missing_attributes_default_safe():
    class Bare:
        pass

    assert segment_is_reliable(Bare(), THRESHOLDS) is True


def test_from_config():
    thresholds = ReliabilityThresholds.from_config(
        {"max_no_speech_prob": 0.5, "min_avg_logprob": -1.0, "max_compression_ratio": 2.0}
    )
    assert thresholds.max_no_speech_prob == 0.5
    seg = FakeSegment(no_speech_prob=0.6)
    assert segment_is_reliable(seg, thresholds) is False
