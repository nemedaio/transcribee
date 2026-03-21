"""Tests for the transcribee CLI."""
import json

import pytest

from transcribee.cli import main, _format_output, _render_srt, _render_vtt, _ts


def test_cli_requires_url():
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_cli_rejects_empty_url():
    with pytest.raises(SystemExit):
        main([""])


def test_format_txt_returns_plain_text():
    result = {"text": "hello world", "language": "en", "segments": []}
    assert _format_output(result, "txt") == "hello world"


def test_format_json_returns_structured_output():
    result = {"text": "hello", "language": "en", "segments": [{"start": 0, "end": 1, "text": "hello"}]}
    output = _format_output(result, "json")
    parsed = json.loads(output)
    assert parsed["text"] == "hello"
    assert parsed["segments"][0]["text"] == "hello"


def test_format_srt_renders_numbered_segments():
    result = {
        "text": "hello world",
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 1.5, "text": "hello"},
            {"start": 1.5, "end": 3.0, "text": "world"},
        ],
    }
    output = _format_output(result, "srt")
    assert "1\n00:00:00,000 --> 00:00:01,500\nhello" in output
    assert "2\n00:00:01,500 --> 00:00:03,000\nworld" in output


def test_format_vtt_renders_webvtt_header():
    result = {
        "text": "test",
        "language": "en",
        "segments": [{"start": 0.0, "end": 1.0, "text": "test"}],
    }
    output = _format_output(result, "vtt")
    assert output.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.000" in output


def test_timestamp_formatting():
    assert _ts(0.0) == "00:00:00.000"
    assert _ts(61.5) == "00:01:01.500"
    assert _ts(3661.123) == "01:01:01.123"


def test_srt_uses_comma_vtt_uses_dot():
    segments = [{"start": 1.5, "end": 3.0, "text": "test"}]
    assert "00:00:01,500" in _render_srt(segments)
    assert "00:00:01.500" in _render_vtt(segments)
