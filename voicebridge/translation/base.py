"""Translation backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TranslationError(Exception):
    """Raised when a backend cannot translate (network, rate-limit, etc.)."""


class TranslationBackend(ABC):
    """A single translation provider (Google, Argos, ...)."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can be used at all (deps installed, models present)."""

    @abstractmethod
    def translate(self, text: str, source: str, target: str) -> str:
        """Translate ``text`` from ``source`` to ``target`` ISO code.

        Raises :class:`TranslationError` on failure so the manager can fall back.
        """
