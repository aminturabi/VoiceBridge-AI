"""Launch the VoiceBridge AI server, benchmark suite, or performance dashboard.

Usage:
    python -m voicebridge            # start the web server
    python -m voicebridge benchmark  # run automated performance benchmark suite
    python -m voicebridge dashboard  # launch live performance monitoring CLI dashboard
"""

from __future__ import annotations

import argparse
import sys

import uvicorn

from voicebridge.benchmarks.runner import BenchmarkRunner
from voicebridge.config import load_config
from voicebridge.logging_conf import configure_logging, get_logger
from voicebridge.metrics.dashboard import LiveDashboard
from voicebridge.metrics.resource_monitor import ResourceMonitor

logger = get_logger(__name__)


def main() -> None:
    config = load_config()
    parser = argparse.ArgumentParser(prog="voicebridge", description="VoiceBridge AI server & benchmarking toolkit")
    parser.add_argument("command", nargs="?", default="server", choices=["server", "benchmark", "dashboard"], help="Command to run")
    parser.add_argument("--host", default=config.get("api.host", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=config.get("api.port", 8000))
    parser.add_argument("--reload", action="store_true", help="auto-reload (dev)")
    args = parser.parse_args()

    configure_logging(config.get("logging.level", "INFO"), config.get("logging.file", None))

    if args.command == "benchmark":
        logger.info("Executing VoiceBridge AI benchmark suite...")
        runner = BenchmarkRunner(config=config)
        runner.run_all()
        return

    if args.command == "dashboard":
        logger.info("Launching VoiceBridge AI live dashboard...")
        res_mon = ResourceMonitor(sample_interval_sec=0.5, temp_dir=config.path("app.temp_chunk_dir"), output_dir=config.path("app.output_dir"))
        res_mon.start()
        dashboard = LiveDashboard(resource_monitor=res_mon)
        try:
            dashboard.start_live()
        except KeyboardInterrupt:
            res_mon.stop()
            print("\nDashboard closed.")
        return

    # Default command: server
    logger.info("Starting VoiceBridge AI on http://%s:%d", args.host, args.port)
    uvicorn.run(
        "voicebridge.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=config.get("logging.level", "INFO").lower(),
    )


if __name__ == "__main__":
    main()
