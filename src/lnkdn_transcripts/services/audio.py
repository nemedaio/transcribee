from dataclasses import dataclass
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Protocol

from lnkdn_transcripts.config import Settings
from lnkdn_transcripts.logging import get_logger

logger = get_logger(__name__)


class AudioPreparationError(RuntimeError):
    """Raised when source media cannot be converted into transcription-ready audio."""


@dataclass
class PreparedAudio:
    local_path: str


class AudioPreparer(Protocol):
    def prepare(self, source_media_path: str) -> PreparedAudio:
        """Extract or normalize transcription-ready audio from a downloaded source file."""


class FfmpegAudioPreparer:
    def __init__(self, settings: Settings) -> None:
        self.output_extension = settings.extracted_audio_format
        self.sample_rate = settings.extracted_audio_sample_rate
        self.channels = settings.extracted_audio_channels

    def prepare(self, source_media_path: str) -> PreparedAudio:
        source_path = Path(source_media_path)
        output_path = source_path.with_suffix(f".{self.output_extension}")
        logger.info("audio.prepare_start source=%s output=%s", source_path, output_path)

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ar",
            str(self.sample_rate),
            "-ac",
            str(self.channels),
            str(output_path),
        ]
        try:
            run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise AudioPreparationError("ffmpeg is not installed or not available on PATH") from exc
        except CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise AudioPreparationError(stderr or "ffmpeg failed to extract audio") from exc

        logger.info("audio.prepare_complete output=%s", output_path)
        return PreparedAudio(local_path=str(output_path))
