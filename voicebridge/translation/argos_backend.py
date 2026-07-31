"""Argos Translate (offline) backend.

Fully offline, MIT-licensed NMT. Used as a fallback so a network blip or a
Google rate-limit does not break a live demo. Language packages are downloaded
once (see ``scripts`` / README); after that no network is needed.
"""

from __future__ import annotations

import threading

from voicebridge.logging_conf import get_logger
from voicebridge.translation.base import TranslationBackend, TranslationError

logger = get_logger(__name__)


class ArgosBackend(TranslationBackend):
    name = "argos"

    def __init__(self):
        self._translate_mod = None
        self._lock = threading.Lock()
        try:
            import argostranslate.translate as translate_mod

            self._translate_mod = translate_mod
        except ImportError:
            logger.info(
                "argostranslate not installed; offline fallback disabled. "
                "Install with: pip install argostranslate"
            )

    def is_available(self) -> bool:
        return self._translate_mod is not None

    def _pair_installed(self, source: str, target: str) -> bool:
        """Check an installed language pair exists for source->target."""
        try:
            langs = self._translate_mod.get_installed_languages()
        except Exception:  # noqa: BLE001
            return False
        by_code = {lang.code: lang for lang in langs}
        src = by_code.get(source)
        tgt = by_code.get(target)
        if not src or not tgt:
            return False
        try:
            return src.get_translation(tgt) is not None
        except Exception:  # noqa: BLE001
            return False

    def translate(self, text: str, source: str, target: str) -> str:
        if not self.is_available():
            raise TranslationError("argostranslate is not installed")

        # Argos wants a concrete source language, not "auto".
        if source in (None, "auto", "unknown"):
            raise TranslationError(
                "Argos needs a concrete source language, got 'auto'"
            )

        # translate() is not documented as thread-safe; serialize per backend.
        with self._lock:
            if not self._pair_installed(source, target):
                raise TranslationError(
                    f"No installed Argos package for {source}->{target}"
                )
            try:
                result = self._translate_mod.translate(text, source, target)
            except Exception as error:  # noqa: BLE001
                raise TranslationError(f"Argos backend failed: {error}") from error

        if not result:
            raise TranslationError("empty translation from Argos")
        return result
