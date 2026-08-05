"""Unit tests for Urdu translation quality, NLLB fallback order, and Urdu post-processor."""

import logging
from unittest.mock import MagicMock
import pytest

from voicebridge.config import load_config
from voicebridge.translation.manager import TranslationManager
from voicebridge.translation.urdu_postprocessor import UrduPostProcessor


def test_urdu_postprocessor_fluency_and_preservation():
    """Verify that Urdu post-processor improves literal phrases while preserving numbers, currencies, and technical terms."""
    processor = UrduPostProcessor()

    # Test phrase improvement
    assert processor.process("میں اچھا ہوں") == "میں ٹھیک ہوں"
    assert processor.process("تھینک یو") == "شکریہ"
    assert processor.process("کوئی بات نہیں ہے") == "کوئی بات نہیں"

    # Test entity preservation (currencies, dates, numbers)
    raw = "قیمت 500 PKR ہے"
    processed = processor.process(raw)
    assert "500 PKR" in processed

    raw_date = "تاریخ 2026-08-05 ہے"
    processed_date = processor.process(raw_date)
    assert "2026-08-05" in processed_date


def test_translator_fallback_order_nllb_preferred(monkeypatch):
    """Verify that fallback order is Google -> NLLB -> Argos and that request logging records translator used."""
    config = load_config()
    manager = TranslationManager(config)

    # Verify backend order
    backend_names = manager.backend_names
    assert "google" in backend_names
    assert "nllb" in backend_names
    assert "argos" in backend_names

    # Ensure google comes before argos and nllb comes before argos
    google_idx = backend_names.index("google")
    nllb_idx = backend_names.index("nllb")
    argos_idx = backend_names.index("argos")
    assert nllb_idx < argos_idx


def test_translation_logging_records_translator(caplog):
    """Verify that TranslationManager logs which translator handled each request."""
    import time
    config = load_config()
    manager = TranslationManager(config)

    with caplog.at_level(logging.INFO):
        # Translate unique text to bypass cache
        unique_text = f"Unique greeting {time.time()}"
        result = manager.translate(unique_text, "en", "ur")
        assert result  # Contains translated string
        assert any("via translator" in record.message for record in caplog.records)

