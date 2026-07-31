"""CLI Interface for running VoiceBridge AI benchmarks."""

from __future__ import annotations

import argparse
import sys

from voicebridge.benchmarks.runner import BenchmarkRunner
from voicebridge.config import load_config
from voicebridge.logging_conf import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(
        description="VoiceBridge AI Performance Benchmarking & Reporting CLI"
    )
    parser.add_argument(
        "--config", type=str, default=None, help="Path to config.yaml"
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO", help="Logging level"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(args.log_level)

    runner = BenchmarkRunner(config=config)
    results = runner.run_all()

    print("\nBenchmark Execution Completed Successfully!")
    print(f"Recorded Scenarios: {len(results.get('scenarios', []))}")
    print(f"Concurrency Levels Tested: {len(results.get('concurrency', []))}")
    print(f"Reports saved to: {config.path('metrics.report_dir', 'logs/reports')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
