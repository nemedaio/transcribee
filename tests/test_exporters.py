"""Tests for all transcript export formats and edge cases."""
import json

import pytest

from transcribee.services.exporters import (
    ExportFormat,
    IncompleteTranscriptError,
    TranscriptExporter,
    UnsupportedExportFormatError,
)
from transcribee.storage.models import JobStatus, TranscriptJob


def _completed_job(**overrides) -> TranscriptJob:
    defaults = dict(
        id="test-job-id",
        source_url="https://example.com/video/1",
        normalized_url="https://example.com/video/1",
        source_domain="example.com",
        provider="generic",
        status=JobStatus.COMPLETED,
        media_title="Test Video Title",
        media_duration_seconds=120,
        transcript_text="Hello world. This is a test.",
        transcript_language="en",
        transcript_segment_count=2,
        transcript_segments_json=json.dumps([
            {"start_seconds": 0.0, "end_seconds": 1.5, "text": "Hello world."},
            {"start_seconds": 1.5, "end_seconds": 3.0, "text": "This is a test."},
        ]),
    )
    defaults.update(overrides)
    return TranscriptJob(**defaults)


@pytest.fixture
def exporter():
    return TranscriptExporter()


# --- Format coverage ---

def test_txt_export_returns_plain_transcript(exporter):
    job = _completed_job()
    result = exporter.export(job, "txt")

    assert result.media_type == "text/plain; charset=utf-8"
    assert result.content == job.transcript_text
    assert result.filename.endswith(".txt")


def test_md_export_includes_metadata_and_transcript(exporter):
    job = _completed_job()
    result = exporter.export(job, "md")

    assert result.media_type == "text/markdown; charset=utf-8"
    assert "# Test Video Title" in result.content
    assert "Provider: generic" in result.content
    assert "Language: en" in result.content
    assert "## Transcript" in result.content
    assert job.transcript_text in result.content
    assert result.filename.endswith(".md")


def test_srt_export_has_numbered_segments_with_timestamps(exporter):
    job = _completed_job()
    result = exporter.export(job, "srt")

    assert result.media_type == "application/x-subrip; charset=utf-8"
    assert "1\n00:00:00,000 --> 00:00:01,500\nHello world." in result.content
    assert "2\n00:00:01,500 --> 00:00:03,000\nThis is a test." in result.content
    assert result.filename.endswith(".srt")


def test_vtt_export_has_webvtt_header_and_segments(exporter):
    job = _completed_job()
    result = exporter.export(job, "vtt")

    assert result.media_type == "text/vtt; charset=utf-8"
    assert result.content.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.500" in result.content
    assert "Hello world." in result.content
    assert result.filename.endswith(".vtt")


def test_srt_uses_comma_separator_vtt_uses_dot(exporter):
    job = _completed_job()
    srt = exporter.export(job, "srt")
    vtt = exporter.export(job, "vtt")

    assert "00:00:01,500" in srt.content
    assert "00:00:01.500" in vtt.content


# --- Error handling ---

def test_export_rejects_unsupported_format(exporter):
    job = _completed_job()
    with pytest.raises(UnsupportedExportFormatError):
        exporter.export(job, "pdf")


def test_export_rejects_empty_format(exporter):
    job = _completed_job()
    with pytest.raises(UnsupportedExportFormatError):
        exporter.export(job, "")


def test_export_rejects_incomplete_job(exporter):
    job = _completed_job(status=JobStatus.FAILED, transcript_text=None)
    with pytest.raises(IncompleteTranscriptError):
        exporter.export(job, "txt")


def test_export_rejects_queued_job(exporter):
    job = _completed_job(status=JobStatus.QUEUED, transcript_text=None)
    with pytest.raises(IncompleteTranscriptError):
        exporter.export(job, "txt")


# --- Edge cases ---

def test_export_without_segments_uses_full_text_as_single_segment(exporter):
    job = _completed_job(transcript_segments_json=None)
    result = exporter.export(job, "srt")

    assert "1\n" in result.content
    assert job.transcript_text in result.content


def test_export_without_media_title_uses_job_id_in_filename(exporter):
    job = _completed_job(media_title=None)
    result = exporter.export(job, "txt")

    assert job.id in result.filename


def test_filename_sanitizes_special_characters(exporter):
    job = _completed_job(media_title="Hello! @World #2024 — Test (Video)")
    result = exporter.export(job, "txt")

    assert " " not in result.filename
    assert "!" not in result.filename
    assert "@" not in result.filename
    assert "#" not in result.filename


def test_md_export_handles_missing_language(exporter):
    job = _completed_job(transcript_language=None)
    result = exporter.export(job, "md")

    assert "Language: unknown" in result.content


def test_timestamp_formatting_handles_hours(exporter):
    job = _completed_job(
        transcript_segments_json=json.dumps([
            {"start_seconds": 3661.5, "end_seconds": 3665.0, "text": "Over an hour in."},
        ]),
    )
    result = exporter.export(job, "srt")

    assert "01:01:01,500" in result.content
