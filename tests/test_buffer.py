"""Unit tests for the stateful sentence buffer with a fake clock."""

from voicebridge.config.loader import Config
from voicebridge.pipeline.buffer import SentenceBuffer


def make_config(**buffer_overrides):
    buffer_section = {
        "word_limit": 10,
        "timeout_seconds": 4,
        "sentence_endings": [".", "?", "!"],
        "noise_phrases": ["subscribe", "thanks for watching"],
    }
    buffer_section.update(buffer_overrides)
    return Config({"buffer": buffer_section})


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_releases_on_sentence_punctuation():
    buf = SentenceBuffer(make_config(), clock=FakeClock())
    assert buf.add("Hello there") == []
    ready = buf.add("how are you?")
    assert ready == ["Hello there how are you?"]
    assert buf.pending_text == ""


def test_releases_on_word_limit():
    buf = SentenceBuffer(make_config(word_limit=5), clock=FakeClock())
    ready = buf.add("one two three four five six")
    assert len(ready) == 1
    assert "one two three four five" in ready[0]


def test_timeout_flush():
    clock = FakeClock()
    buf = SentenceBuffer(make_config(timeout_seconds=4), clock=clock)
    assert buf.add("an unfinished thought") == []
    assert buf.flush_on_timeout() == []  # not enough time yet
    clock.advance(5)
    assert buf.flush_on_timeout() == ["an unfinished thought"]


def test_noise_fragment_rejected():
    buf = SentenceBuffer(make_config(), clock=FakeClock())
    assert buf.add("subscribe") == []
    assert buf.pending_text == ""


def test_lone_word_rejected_when_empty():
    buf = SentenceBuffer(make_config(), clock=FakeClock())
    assert buf.add("okay") == []
    assert buf.pending_text == ""


def test_lone_word_accepted_when_buffer_has_text():
    buf = SentenceBuffer(make_config(), clock=FakeClock())
    buf.add("please stop the")
    buf.add("car")
    assert "car" in buf.pending_text


def test_multiple_sentences_in_one_fragment():
    buf = SentenceBuffer(make_config(), clock=FakeClock())
    ready = buf.add("First one. Second one! A tail")
    assert ready == ["First one.", "Second one!"]
    assert buf.pending_text == "A tail"


def test_force_flush_empty_returns_nothing():
    buf = SentenceBuffer(make_config(), clock=FakeClock())
    assert buf.force_flush() == []
