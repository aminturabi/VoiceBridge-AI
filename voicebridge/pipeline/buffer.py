"""Stateful sentence buffer.

Accumulates transcribed fragments and decides when to release text to
translation, using the pure helpers in :mod:`voicebridge.pipeline.text_utils`.

Release triggers (from the prototype, now config-driven):
* a complete sentence (ends with sentence punctuation),
* the buffer reaches the word limit,
* the speaker pauses longer than the timeout.

All wall-clock decisions go through an injectable ``clock`` so the buffer can
be unit tested deterministically.
"""

from __future__ import annotations

import time
from typing import Callable

from voicebridge.config import Config
from voicebridge.pipeline.text_utils import (
    clean_text,
    count_words,
    should_accept_fragment,
    should_translate_sentence,
    split_complete_sentences,
)


class SentenceBuffer:
    """Collects fragments and yields translation-ready sentences."""

    def __init__(self, config: Config, clock: Callable[[], float] = time.monotonic):
        buffer_cfg = config.get("buffer", {})
        self._word_limit = int(buffer_cfg.get("word_limit", 10))
        self._timeout = float(buffer_cfg.get("timeout_seconds", 4))
        self._endings = tuple(buffer_cfg.get("sentence_endings", (".", "?", "!")))
        self._noise = frozenset(
            p.casefold() for p in buffer_cfg.get("noise_phrases", [])
        )
        self._clock = clock

        self._buffer = ""
        self._last_update = clock()

    @property
    def pending_text(self) -> str:
        return self._buffer

    def add(self, fragment: str) -> list[str]:
        """Add a transcribed fragment; return any sentences ready to translate."""
        fragment = clean_text(fragment)
        has_text = bool(self._buffer)

        if not should_accept_fragment(
            fragment, has_text, noise_phrases=self._noise, endings=self._endings
        ):
            return []

        self._buffer = f"{self._buffer} {fragment}".strip() if has_text else fragment
        self._last_update = self._clock()
        return self._drain()

    def _drain(self) -> list[str]:
        ready: list[str] = []

        # 1) Release any complete, punctuated sentences.
        complete, remainder = split_complete_sentences(self._buffer, self._endings)
        for sentence in complete:
            if should_translate_sentence(
                sentence, noise_phrases=self._noise, endings=self._endings
            ):
                ready.append(sentence)
        self._buffer = remainder

        # 2) Release on word limit even without punctuation.
        if count_words(self._buffer) >= self._word_limit:
            if should_translate_sentence(
                self._buffer, noise_phrases=self._noise, endings=self._endings
            ):
                ready.append(self._buffer)
            self._buffer = ""

        return ready

    def flush_on_timeout(self) -> list[str]:
        """Release the buffer if the pause since last update exceeds timeout."""
        if not self._buffer:
            return []
        if self._clock() - self._last_update < self._timeout:
            return []
        return self.force_flush()

    def force_flush(self) -> list[str]:
        """Unconditionally release whatever is buffered (e.g. at shutdown)."""
        text = self._buffer
        self._buffer = ""
        self._last_update = self._clock()
        if text and should_translate_sentence(
            text, noise_phrases=self._noise, endings=self._endings
        ):
            return [text]
        return []
