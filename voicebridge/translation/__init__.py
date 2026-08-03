"""Translation package exports."""

from voicebridge.translation.argos_backend import ArgosBackend
from voicebridge.translation.base import TranslationBackend, TranslationError
from voicebridge.translation.google_backend import GoogleBackend
from voicebridge.translation.manager import TranslationManager
from voicebridge.translation.nllb_backend import NllbBackend

__all__ = [
    "TranslationBackend",
    "TranslationError",
    "ArgosBackend",
    "GoogleBackend",
    "NllbBackend",
    "TranslationManager",
]
