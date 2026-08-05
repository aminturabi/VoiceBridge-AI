"""Central logging setup for VoiceBridge AI.

Replaces the prototype's ``print``-based ``log()`` with the standard
``logging`` module: leveled, timestamped, optionally written to a file, and
safe to call once at startup.
"""

from __future__ import annotations

import contextvars
import logging
import sys
from pathlib import Path

_CONFIGURED = False

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        return True

_FORMAT = "%(asctime)s | %(levelname)-7s | [%(request_id)s] | %(name)s | %(message)s"
_DATEFMT = "%H:%M:%S"


def configure_logging(level: str = "INFO", log_file: str | Path | None = None) -> None:
    """Configure the root logger once.

    Args:
        level: one of DEBUG/INFO/WARNING/ERROR (case-insensitive).
        log_file: optional path; if given, logs are written there as well as
            to the console.
    """
    global _CONFIGURED

    root = logging.getLogger()
    numeric_level = getattr(logging, str(level).upper(), logging.INFO)
    root.setLevel(numeric_level)

    if _CONFIGURED:
        # Reconfigure level on repeat calls but don't stack handlers.
        for handler in root.handlers:
            handler.setLevel(numeric_level)
        return

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)
    req_filter = RequestIDFilter()

    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(formatter)
    console.setLevel(numeric_level)
    console.addFilter(req_filter)
    root.addHandler(console)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_level)
        file_handler.addFilter(req_filter)
        root.addHandler(file_handler)

    # Quiet down noisy third-party loggers.
    for noisy in ("faster_whisper", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger. Callers use ``get_logger(__name__)``."""
    return logging.getLogger(name)

