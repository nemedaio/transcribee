import json
import re
from dataclasses import dataclass
from enum import Enum

from transcribee.logging import get_logger
from transcribee.services.transcriber import TranscriptSegment
from transcribee.storage.models import JobStatus, TranscriptJob

logger = get_logger(__name__)


class UnsupportedExportFormatError(ValueError):
    """Raised when the requested transcript export format is not supported."""


class IncompleteTranscriptError(ValueError):
    """Raised when a job has no completed transcript available for export."""


class ExportFormat(str, Enum):
    TXT = "txt"
    MD = "md"
    SRT = "srt"
    VTT = "vtt"


@dataclass
class ExportedTranscript:
    filename: str
    media_type: str
    content: str


class TranscriptExporter:
    def export(self, job: TranscriptJob, format_name: str) -> ExportedTranscript:
        if job.status != JobStatus.COMPLETED or not job.transcript_text:
            raise IncompleteTranscriptError("Transcript is not available for export yet")

        try:
            export_format = ExportFormat(format_name)
        except ValueError as exc:
            raise UnsupportedExportFormatError(format_name) from exc

        stem = self._filename_stem(job)
        logger.info("exports.generate job_id=%s format=%s", job.id, export_format.value)

        if export_format is ExportFormat.TXT:
            return ExportedTranscript(
                filename=f"{stem}.txt",
                media_type="text/plain; charset=utf-8",
                content=job.transcript_text,
            )
        if export_format is ExportFormat.MD:
            return ExportedTranscript(
                filename=f"{stem}.md",
                media_type="text/markdown; charset=utf-8",
                content=self._render_markdown(job),
            )
        if export_format is ExportFormat.SRT:
            return ExportedTranscript(
                filename=f"{stem}.srt",
                media_type="application/x-subrip; charset=utf-8",
                content=self._render_srt(job),
            )
        return ExportedTranscript(
            filename=f"{stem}.vtt",
            media_type="text/vtt; charset=utf-8",
            content=self._render_vtt(job),
        )

    def _render_markdown(self, job: TranscriptJob) -> str:
        lines = [
            f"# {job.media_title or job.id}",
            "",
            f"- Provider: {job.provider}",
            f"- Source URL: {job.normalized_url}",
            f"- Language: {job.transcript_language or 'unknown'}",
            "",
            "## Transcript",
            "",
            job.transcript_text or "",
        ]
        return "\n".join(lines).strip() + "\n"

    def _render_srt(self, job: TranscriptJob) -> str:
        segments = self._segments(job)
        blocks = []
        for index, segment in enumerate(segments, start=1):
            blocks.append(
                "\n".join(
                    [
                        str(index),
                        f"{self._format_timestamp(segment.start_seconds, separator=',')} --> "
                        f"{self._format_timestamp(segment.end_seconds, separator=',')}",
                        segment.text,
                    ]
                )
            )
        return "\n\n".join(blocks).strip() + "\n"

    def _render_vtt(self, job: TranscriptJob) -> str:
        segments = self._segments(job)
        blocks = ["WEBVTT"]
        for segment in segments:
            blocks.append(
                "\n".join(
                    [
                        "",
                        f"{self._format_timestamp(segment.start_seconds)} --> "
                        f"{self._format_timestamp(segment.end_seconds)}",
                        segment.text,
                    ]
                )
            )
        return "\n".join(blocks).strip() + "\n"

    def _segments(self, job: TranscriptJob) -> list[TranscriptSegment]:
        if not job.transcript_segments_json:
            return [
                TranscriptSegment(
                    start_seconds=0.0,
                    end_seconds=float(job.media_duration_seconds or 0),
                    text=job.transcript_text or "",
                )
            ]

        raw_segments = json.loads(job.transcript_segments_json)
        return [
            TranscriptSegment(
                start_seconds=float(segment["start_seconds"]),
                end_seconds=float(segment["end_seconds"]),
                text=segment["text"],
            )
            for segment in raw_segments
        ]

    @staticmethod
    def _filename_stem(job: TranscriptJob) -> str:
        source = job.media_title or job.id
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", source.strip().lower()).strip("-")
        return cleaned or job.id

    @staticmethod
    def _format_timestamp(seconds: float, separator: str = ".") -> str:
        total_milliseconds = round(seconds * 1000)
        hours, remainder = divmod(total_milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, milliseconds = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{secs:02}{separator}{milliseconds:03}"
