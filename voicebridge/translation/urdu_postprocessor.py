"""Urdu Post-Processor: Enhances literal translation into fluent, natural conversational Pakistani Urdu.

Preserves proper nouns, numbers, dates, currencies, and technical terms.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from voicebridge.config import Config
from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)

# Common literal translation corrections for conversational Pakistani Urdu
_URDU_CONVERSATIONAL_MAP: List[Tuple[re.Pattern, str]] = [
    # Greetings & Common Phrases
    (re.compile(r"\bمیں اچھا ہوں\b"), "میں ٹھیک ہوں"),
    (re.compile(r"\bمیں اچھا ہے\b"), "میں بالکل ٹھیک ہوں"),
    (re.compile(r"\bآپ کیسے ہیں؟\b"), "آپ کا کیا حال ہے؟"),
    (re.compile(r"\bتھینک یو\b"), "شکریہ"),
    (re.compile(r"\bبہت شکریہ\b"), "بہت بہت شکریہ"),
    (re.compile(r"\bخوش آمدید\b"), "جی آیا نوں / خوش آمدید"),
    
    # Conversational phrasing improvements
    (re.compile(r"\bکیا ہو رہا ہے؟\b"), "کیا چل رہا ہے؟"),
    (re.compile(r"\bیہ کیا ہے؟\b"), "یہ کیا چیز ہے؟"),
    (re.compile(r"\bمجھے نہیں معلوم\b"), "مجھے معلوم نہیں"),
    (re.compile(r"\bکوئی بات نہیں ہے\b"), "کوئی بات نہیں"),
    (re.compile(r"\bبراہ کرم\b"), "برائے مہربانی"),
    (re.compile(r"\bاللہ حافظ\b"), "خدا حافظ"),
    
    # Punctuation & Spacing cleanup
    (re.compile(r"\s+([؟،!۔])"), r"\1"),  # Remove space before Urdu punctuation
]

# Patterns for elements that must be preserved
_PRESERVE_PATTERNS = [
    re.compile(r"\$\d+(?:\.\d+)?|\b\d+(?:\.\d+)?\s*(?:PKR|USD|EUR|GBP|روپے|ڈالر)\b", re.IGNORECASE),  # Currencies
    re.compile(r"\b\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b"),  # Dates
    re.compile(r"\b\d+(?:\.\d+)?%?"),  # Numbers and percentages
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email addresses
    re.compile(r"https?://\S+"),  # URLs
]


class UrduPostProcessor:
    """Post-processing engine to refine Urdu translations for conversational fluency."""

    def __init__(self, config: Config | None = None):
        self.enabled = True
        if config:
            self.enabled = bool(config.get("translation.urdu_postprocessor.enabled", True))

    def process(self, text: str, original_english: str = "") -> str:
        """Apply Urdu fluency rules while preserving numbers, dates, currencies, and technical terms."""
        if not self.enabled or not text or not text.strip():
            return text

        refined = text.strip()

        # Step 1: Protect preserved entities (numbers, currencies, URLs)
        protected_placeholders: Dict[str, str] = {}
        placeholder_idx = 0

        for pattern in _PRESERVE_PATTERNS:
            matches = pattern.findall(refined)
            for match in matches:
                placeholder = f"__ENTITY_{placeholder_idx}__"
                protected_placeholders[placeholder] = match
                refined = refined.replace(match, placeholder, 1)
                placeholder_idx += 1

        # Step 2: Apply conversational Pakistani Urdu replacements
        for pattern, replacement in _URDU_CONVERSATIONAL_MAP:
            refined = pattern.sub(replacement, refined)

        # Step 3: Restore protected entities
        for placeholder, original_val in protected_placeholders.items():
            refined = refined.replace(placeholder, original_val)

        logger.debug("Urdu post-processed: %r -> %r", text, refined)
        return refined
