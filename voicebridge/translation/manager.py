"""Translation manager: tries configured backends in order with retry/backoff & caching.

Order and retry policy come from ``config.translation``. Each backend is
retried with exponential backoff before moving to the next one. Results are
cached in the translation cache layer.
"""

from __future__ import annotations

import random
import time

from voicebridge.cache import TranslationCache
from voicebridge.config import Config
from voicebridge.logging_conf import get_logger
from voicebridge.translation.argos_backend import ArgosBackend
from voicebridge.translation.base import TranslationBackend, TranslationError
from voicebridge.translation.google_backend import GoogleBackend
from voicebridge.translation.nllb_backend import NllbBackend

logger = get_logger(__name__)

_BACKEND_REGISTRY = {
    "nllb": NllbBackend,
    "google": GoogleBackend,
    "argos": ArgosBackend,
}


class TranslationManager:
    """Resilient multi-backend translator with caching support."""

    def __init__(self, config: Config):
        self._config = config
        self._cache = TranslationCache(config)

        retry = config.get("translation.retry", {})
        self._max_attempts = int(retry.get("max_attempts", 3))
        self._base_delay = float(retry.get("base_delay_seconds", 0.5))
        self._max_delay = float(retry.get("max_delay_seconds", 4.0))

        self._backends: list[TranslationBackend] = []

        # Support primary 'provider' or 'backends' list in configuration
        primary_provider = config.get("translation.provider", None)
        configured_backends = config.get("translation.backends", ["nllb", "google", "argos"])

        backend_names = list(configured_backends)
        if primary_provider and primary_provider not in backend_names:
            backend_names.insert(0, primary_provider)
        elif primary_provider and primary_provider in backend_names:
            backend_names.remove(primary_provider)
            backend_names.insert(0, primary_provider)

        for name in backend_names:
            backend_cls = _BACKEND_REGISTRY.get(name)
            if backend_cls is None:
                logger.warning("Unknown translation backend %r; skipping", name)
                continue

            try:
                # Some backends accept config argument (like NllbBackend)
                backend = backend_cls(config) if backend_cls is NllbBackend else backend_cls()
            except TypeError:
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
        """Translate, checking cache first, then trying backends with retry."""
        if not text:
            return ""
        if source == target:
            return text

        # Check translation cache
        cached = self._cache.get(text, source, target)
        if cached:
            return cached

        last_error: Exception | None = None

        for backend in self._backends:
            for attempt in range(self._max_attempts):
                try:
                    result = backend.translate(text, source, target)
                    if attempt or backend is not self._backends[0]:
                        logger.info(
                            "Translated via %s (attempt %d)", backend.name, attempt + 1
                        )

                    # Store in cache
                    self._cache.set(text, source, target, result)
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
