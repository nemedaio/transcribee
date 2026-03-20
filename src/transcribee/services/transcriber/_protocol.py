from dataclasses import dataclass
from typing import Protocol


class TranscriptionError(RuntimeError):
    """Raised when fetched media cannot be transcribed."""


@dataclass
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass
class TranscriptionResult:
    text: str
    language: str | None
    segments: list[TranscriptSegment]


class MediaTranscriber(Protocol):
    def transcribe(self, media_file_path: str) -> TranscriptionResult:
        """Return transcript output for a local media file."""
