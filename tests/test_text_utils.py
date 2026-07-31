"""Unit tests for the pure text-processing logic."""

import pytest

from voicebridge.pipeline.text_utils import (
    clean_text,
    count_words,
    ends_with_sentence_punctuation,
    looks_like_noise,
    should_accept_fragment,
    should_translate_sentence,
    split_complete_sentences,
)


class TestCleanText:
    def test_collapses_whitespace(self):
        assert clean_text("hello   world") == "hello world"

    def test_strips_newlines_and_tabs(self):
        assert clean_text("hello\n\r\tworld ") == "hello world"

    def test_empty_and_none_safe(self):
        assert clean_text("") == ""
        assert clean_text("   ") == ""

    def test_preserves_arabic(self):
        assert clean_text("  مرحبا   بك  ") == "مرحبا بك"


class TestCountWords:
    def test_basic_english(self):
        assert count_words("one two three") == 3

    def test_ignores_pure_punctuation(self):
        assert count_words("hello , . ! world") == 2

    def test_hyphen_and_apostrophe_kept(self):
        assert count_words("don't stop") == 2
        assert count_words("state-of-the-art") == 1

    def test_arabic_words(self):
        assert count_words("مرحبا بك") == 2

    def test_empty(self):
        assert count_words("") == 0
        assert count_words("!!! ???") == 0


class TestEndsWithSentencePunctuation:
    @pytest.mark.parametrize("text", ["Hello.", "What?", "Stop!", "مرحبا؟", "ختم۔"])
    def test_true_cases(self, text):
        assert ends_with_sentence_punctuation(text) is True

    @pytest.mark.parametrize("text", ["Hello", "half a sentence", ""])
    def test_false_cases(self, text):
        assert ends_with_sentence_punctuation(text) is False

    def test_trailing_space_still_detected(self):
        assert ends_with_sentence_punctuation("Done.   ") is True


class TestLooksLikeNoise:
    def test_empty_is_noise(self):
        assert looks_like_noise("") is True
        assert looks_like_noise("   ") is True

    def test_known_phrases(self):
        assert looks_like_noise("thanks for watching") is True
        assert looks_like_noise("Please Subscribe") is True

    def test_only_punctuation(self):
        assert looks_like_noise("...!!!") is True

    def test_non_speech_tags(self):
        assert looks_like_noise("[music]") is True
        assert looks_like_noise("(applause)") is True
        assert looks_like_noise("silence") is True

    def test_repeated_word(self):
        assert looks_like_noise("no no no no") is True

    def test_repeated_letters(self):
        assert looks_like_noise("aaaaaaaaaa") is True

    def test_real_sentence_is_not_noise(self):
        assert looks_like_noise("Hello, how are you today?") is False

    def test_arabic_sentence_not_noise(self):
        assert looks_like_noise("كيف حالك اليوم؟") is False


class TestSplitCompleteSentences:
    def test_no_punctuation_all_remainder(self):
        complete, remainder = split_complete_sentences("this is unfinished")
        assert complete == []
        assert remainder == "this is unfinished"

    def test_single_sentence(self):
        complete, remainder = split_complete_sentences("Hello world.")
        assert complete == ["Hello world."]
        assert remainder == ""

    def test_multiple_sentences_with_tail(self):
        complete, remainder = split_complete_sentences("One. Two! A tail")
        assert complete == ["One.", "Two!"]
        assert remainder == "A tail"

    def test_arabic_question_mark(self):
        complete, remainder = split_complete_sentences("كيف حالك؟ انا بخير")
        assert complete == ["كيف حالك؟"]
        assert remainder == "انا بخير"

    def test_custom_endings(self):
        complete, remainder = split_complete_sentences("a|b|c", endings=("|",))
        assert complete == ["a|", "b|"]
        assert remainder == "c"


class TestShouldAcceptFragment:
    def test_noise_rejected(self):
        assert should_accept_fragment("[music]", buffer_has_text=False) is False

    def test_lone_word_rejected_when_buffer_empty(self):
        assert should_accept_fragment("hello", buffer_has_text=False) is False

    def test_lone_word_accepted_when_buffer_has_text(self):
        assert should_accept_fragment("hello", buffer_has_text=True) is True

    def test_lone_word_with_punctuation_accepted(self):
        assert should_accept_fragment("Yes!", buffer_has_text=False) is True

    def test_multiword_accepted(self):
        assert should_accept_fragment("hello there", buffer_has_text=False) is True


class TestShouldTranslateSentence:
    def test_noise_rejected(self):
        assert should_translate_sentence("subscribe") is False

    def test_lone_word_without_punct_rejected(self):
        assert should_translate_sentence("okay") is False

    def test_lone_word_with_punct_accepted(self):
        assert should_translate_sentence("Okay!") is True

    def test_full_sentence_accepted(self):
        assert should_translate_sentence("How are you doing today") is True

    def test_whitespace_normalized_before_check(self):
        assert should_translate_sentence("  hello   world  ") is True
