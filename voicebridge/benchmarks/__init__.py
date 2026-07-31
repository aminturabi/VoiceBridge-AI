"""VoiceBridge AI Benchmark Suite package."""

from voicebridge.benchmarks.audio_generator import generate_benchmark_wav
from voicebridge.benchmarks.runner import BenchmarkRunner

__all__ = ["generate_benchmark_wav", "BenchmarkRunner"]
