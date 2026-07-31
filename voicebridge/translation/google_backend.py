"""deep-translator (Google) backend.

Note (documented limitation): deep-translator hits Google's unofficial free
endpoint. It needs no API key but is undocumented and rate-limited, so it can
fail mid-demo. The manager pairs it with retry/backoff and an offline fallback.
"""

from __future__ import annotations

from voicebridge.logging_conf import get_logger
from voicebridge.translation.base import TranslationBackend, TranslationError

logger = get_logger(__name__)


class GoogleBackend(TranslationBackend):
    name = "google"

    def __init__(self):
        self._GoogleTranslator = None
        try:
            from deep_translator import GoogleTranslator

            self._GoogleTranslator = GoogleTranslator
        except ImportError as error:
            logger.warning("deep-translator not installed: %s", error)

    def is_available(self) -> bool:
        return self._GoogleTranslator is not None

    def translate(self, text: str, source: str, target: str) -> str:
        if not self.is_available():
            raise TranslationError("deep-translator is not installed")
        try:
            # source="auto" lets Google detect; keeps prototype behaviour.
            translator = self._GoogleTranslator(source="auto", target=target)
            result = translator.translate(text)
            if not result:
                raise TranslationError("empty translation from Google")
            return result
        except TranslationError:
            raise
        except Exception as error:  # noqa: BLE001 - normalize to TranslationError
            raise TranslationError(f"Google backend failed: {error}") from error
