"""Translation manager: tries configured backends in order with retry/backoff.

Order and retry policy come from ``config.translation``. Each backend is
retried with exponential backoff before moving to the next one, so a transient
Google rate-limit gets a couple of retries, then falls through to offline Argos.
"""

from __future__ import annotations

import random
import time

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.translation.argos_backend import ArgosBackend
from voicebridge.translation.base import TranslationBackend, TranslationError
from voicebridge.translation.google_backend import GoogleBackend

logger = get_logger(__name__)

_BACKEND_REGISTRY = {
    "google": GoogleBackend,
    "argos": ArgosBackend,
}


class TranslationManager:
    """Resilient multi-backend translator."""

    def __init__(self, config: Config):
        self._config = config
        retry = config.get("translation.retry", {})
        self._max_attempts = int(retry.get("max_attempts", 3))
        self._base_delay = float(retry.get("base_delay_seconds", 0.5))
        self._max_delay = float(retry.get("max_delay_seconds", 4.0))

        self._backends: list[TranslationBackend] = []
        for name in config.get("translation.backends", ["google"]):
            backend_cls = _BACKEND_REGISTRY.get(name)
            if backend_cls is None:
                logger.warning("Unknown translation backend %r; skipping", name)
                continue
            backend = backend_cls()
            if backend.is_available():
                self._backends.append(backend)
                logger.info("Translation backend enabled: %s", name)
            else:
                logger.info("Translation backend %r unavailable; skipping", name)

        if not self._backends:
            logger.error("No translation backends available!")

    @property
    def backend_names(self) -> list[str]:
        return [b.name for b in self._backends]

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter, capped at max_delay."""
        delay = min(self._base_delay * (2 ** attempt), self._max_delay)
        return delay + random.uniform(0, delay * 0.1)

    def translate(self, text: str, source: str, target: str) -> str:
        """Translate, trying each backend with retries. Raises on total failure."""
        if not text:
            return ""
        if source == target:
            return text

        last_error: Exception | None = None

        for backend in self._backends:
            for attempt in range(self._max_attempts):
                try:
                    result = backend.translate(text, source, target)
                    if attempt or backend is not self._backends[0]:
                        logger.info(
                            "Translated via %s (attempt %d)", backend.name, attempt + 1
                        )
                    return result
                except TranslationError as error:
                    last_error = error
                    is_last_attempt = attempt == self._max_attempts - 1
                    if is_last_attempt:
                        logger.warning(
                            "Backend %s failed after %d attempts: %s",
                            backend.name, self._max_attempts, error,
                        )
                    else:
                        delay = self._backoff_delay(attempt)
                        logger.debug(
                            "Backend %s attempt %d failed (%s); retrying in %.2fs",
                            backend.name, attempt + 1, error, delay,
                        )
                        time.sleep(delay)

        raise TranslationError(
            f"All translation backends failed for {source}->{target}. "
            f"Last error: {last_error}"
        )
