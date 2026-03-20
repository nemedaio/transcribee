"""Tests for Deepgram word-to-segment grouping logic."""
from transcribee.services.transcriber._deepgram import DeepgramTranscriber


def test_empty_words_returns_empty_segments():
    assert DeepgramTranscriber._words_to_segments([]) == []


def test_single_word_returns_one_segment():
    words = [{"word": "hello", "start": 0.0, "end": 0.5}]

    segments = DeepgramTranscriber._words_to_segments(words)

    assert len(segments) == 1
    assert segments[0].text == "hello"
    assert segments[0].start_seconds == 0.0
    assert segments[0].end_seconds == 0.5


def test_consecutive_words_group_into_one_segment():
    words = [
        {"word": "hello", "start": 0.0, "end": 0.3},
        {"word": "world", "start": 0.4, "end": 0.8},
        {"word": "today", "start": 0.9, "end": 1.2},
    ]

    segments = DeepgramTranscriber._words_to_segments(words)

    assert len(segments) == 1
    assert segments[0].text == "hello world today"
    assert segments[0].start_seconds == 0.0
    assert segments[0].end_seconds == 1.2


def test_large_gap_splits_into_separate_segments():
    words = [
        {"word": "first", "start": 0.0, "end": 0.5},
        {"word": "sentence", "start": 0.6, "end": 1.0},
        {"word": "second", "start": 3.0, "end": 3.5},
        {"word": "sentence", "start": 3.6, "end": 4.0},
    ]

    segments = DeepgramTranscriber._words_to_segments(words, max_gap=1.0)

    assert len(segments) == 2
    assert segments[0].text == "first sentence"
    assert segments[0].start_seconds == 0.0
    assert segments[0].end_seconds == 1.0
    assert segments[1].text == "second sentence"
    assert segments[1].start_seconds == 3.0
    assert segments[1].end_seconds == 4.0


def test_custom_max_gap_controls_splitting():
    words = [
        {"word": "a", "start": 0.0, "end": 0.2},
        {"word": "b", "start": 0.7, "end": 0.9},
    ]

    tight = DeepgramTranscriber._words_to_segments(words, max_gap=0.3)
    loose = DeepgramTranscriber._words_to_segments(words, max_gap=1.0)

    assert len(tight) == 2
    assert len(loose) == 1


def test_words_with_missing_fields_use_defaults():
    words = [
        {"word": "hello"},
        {"word": "world"},
    ]

    segments = DeepgramTranscriber._words_to_segments(words)

    assert len(segments) == 1
    assert segments[0].text == "hello world"


def test_multiple_gaps_create_multiple_segments():
    words = [
        {"word": "one", "start": 0.0, "end": 0.3},
        {"word": "two", "start": 5.0, "end": 5.3},
        {"word": "three", "start": 10.0, "end": 10.3},
    ]

    segments = DeepgramTranscriber._words_to_segments(words, max_gap=1.0)

    assert len(segments) == 3
    assert [s.text for s in segments] == ["one", "two", "three"]
