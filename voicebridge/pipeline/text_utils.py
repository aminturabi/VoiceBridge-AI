"""Pure text-processing logic for the buffering/translation stages.

These functions are deliberately side-effect free (no I/O, no globals) so they
are easy to unit test. Config-derived values — sentence endings, noise phrases,
the word limit — are passed in explicitly rather than read from globals.

Ported and cleaned up from the original prototype's helper functions.
"""

from __future__ import annotations

import re

# Default sentence-ending marks (EN + Arabic question mark/full stop + Urdu +
# Devanagari danda). Callers normally pass the config list, but this keeps the
# module usable standalone.
DEFAULT_SENTENCE_ENDINGS: tuple[str, ...] = (".", "?", "!", "؟", "۔", "।")

DEFAULT_NOISE_PHRASES: frozenset[str] = frozenset(
    {
        "thanks",
        "thank you",
        "thank you so much",
        "thank you very much",
        "thanks for watching",
        "thank you for watching",
        "please subscribe",
        "subscribe",
        "subtitles",
        "subtitles by",
        "translated by",
        "amara org",
        "bye",
    }
)

# Bracketed non-speech tags Whisper commonly emits on silence/noise.
_NON_SPEECH_TAG = re.compile(r"[\[(]?(music|noise|silence|applause)[\])]?")
_ONLY_PUNCT = re.compile(r"[\W_]+")


def clean_text(text: str) -> str:
    """Normalize whitespace while keeping multilingual text unchanged."""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def count_words(text: str) -> int:
    """Count words in a way that works for English, Arabic, Urdu, etc."""
    text = re.sub(r"[^\w\s'-]", " ", text, flags=re.UNICODE)
    words = [word for word in text.split() if any(ch.isalnum() for ch in word)]
    return len(words)


def ends_with_sentence_punctuation(
    text: str, endings: tuple[str, ...] = DEFAULT_SENTENCE_ENDINGS
) -> bool:
    """True if the cleaned text ends with a sentence-ending mark."""
    cleaned = clean_text(text)
    return bool(cleaned) and cleaned.endswith(tuple(endings))


def looks_like_noise(
    text: str, noise_phrases: frozenset[str] = DEFAULT_NOISE_PHRASES
) -> bool:
    """Reject empty/noisy STT outputs before they enter the buffer."""
    text = clean_text(text)
    if not text:
        return True

    lower_text = text.casefold()
    # Strip punctuation to accurately catch noise phrases even when punctuated
    stripped_text = re.sub(r"[^\w\s]", "", lower_text).strip()

    normalized_noise = {p.casefold() for p in noise_phrases}
    if lower_text in normalized_noise or stripped_text in normalized_noise:
        return True
    if _ONLY_PUNCT.fullmatch(text):
        return True
    if _NON_SPEECH_TAG.fullmatch(lower_text):
        return True

    # Same word repeated many times = stuck/hallucinated output.
    words = lower_text.split()
    if len(words) >= 4 and len(set(words)) == 1:
        return True

    # Long run of one or two distinct letters = garbage.
    letters = [ch for ch in lower_text if ch.isalpha()]
    if len(letters) > 8 and len(set(letters)) <= 2:
        return True

    return False


def split_complete_sentences(
    text: str, endings: tuple[str, ...] = DEFAULT_SENTENCE_ENDINGS
) -> tuple[list[str], str]:
    """Return (complete punctuated sentences, unfinished tail)."""
    complete_sentences: list[str] = []
    start_index = 0
    ending_set = set(endings)

    for index, char in enumerate(text):
        if char in ending_set:
            sentence = clean_text(text[start_index : index + 1])
            if sentence:
                complete_sentences.append(sentence)
            start_index = index + 1

    remainder = clean_text(text[start_index:])
    return complete_sentences, remainder


def should_accept_fragment(
    text: str,
    buffer_has_text: bool,
    *,
    noise_phrases: frozenset[str] = DEFAULT_NOISE_PHRASES,
    endings: tuple[str, ...] = DEFAULT_SENTENCE_ENDINGS,
) -> bool:
    """Ignore one-word unclear fragments unless they complete a sentence."""
    if looks_like_noise(text, noise_phrases):
        return False

    if count_words(text) <= 1 and not ends_with_sentence_punctuation(text, endings):
        # A lone word is only useful if it continues an existing buffer.
        return buffer_has_text

    return True


def should_translate_sentence(
    sentence: str,
    *,
    noise_phrases: frozenset[str] = DEFAULT_NOISE_PHRASES,
    endings: tuple[str, ...] = DEFAULT_SENTENCE_ENDINGS,
) -> bool:
    """Final guard before translation."""
    sentence = clean_text(sentence)

    if looks_like_noise(sentence, noise_phrases):
        return False

    if count_words(sentence) <= 1 and not ends_with_sentence_punctuation(
        sentence, endings
    ):
        return False

    return True
