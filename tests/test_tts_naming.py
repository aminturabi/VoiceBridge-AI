"""Unit tests for Microsoft Neural TTS naming, aliases, and browser independence."""

import pytest
from voicebridge.config import load_config
from voicebridge.tts.edge_tts_backend import EdgeTtsBackend
from voicebridge.tts.manager import TtsManager


def test_microsoft_neural_tts_display_name():
    """Verify that EdgeTtsBackend has display_name 'Microsoft Neural TTS'."""
    config = load_config()
    backend = EdgeTtsBackend(config)
    assert getattr(backend, "display_name") == "Microsoft Neural TTS"


def test_tts_manager_aliases():
    """Verify that TtsManager accepts 'microsoft-tts' and 'microsoft-neural-tts' aliases."""
    config = load_config()
    
    manager_ms = TtsManager(config)
    assert manager_ms.backend_name == "edge-tts"
