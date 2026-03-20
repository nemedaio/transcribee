from pathlib import Path

from transcribee.config import Settings
from transcribee.logging import get_logger
from transcribee.services.transcriber._protocol import (
    TranscriptionError,
    TranscriptionResult,
    TranscriptSegment,
)

logger = get_logger(__name__)


class OpenAIApiTranscriber:
    """Transcribes audio via the OpenAI Whisper API. Requires OPENAI_API_KEY."""

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_api_base_url
        self.model = settings.openai_whisper_model
        if not self.api_key:
            raise TranscriptionError(
                "The openai-api backend requires OPENAI_API_KEY to be set in your environment."
            )

    def transcribe(self, media_file_path: str) -> TranscriptionResult:
        logger.info(
            "transcriber.start path=%s model=%s backend=openai-api",
            media_file_path,
            self.model,
        )
        try:
            client = self._create_client()
            with open(media_file_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model=self.model,
                    file=(Path(media_file_path).name, audio_file),
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc

        segments = [
            TranscriptSegment(
                start_seconds=seg.get("start", 0.0),
                end_seconds=seg.get("end", 0.0),
                text=seg.get("text", "").strip(),
            )
            for seg in (getattr(response, "segments", None) or [])
        ]
        text = getattr(response, "text", "") or ""
        language = getattr(response, "language", None)

        logger.info(
            "transcriber.complete path=%s language=%s segments=%s",
            media_file_path,
            language,
            len(segments),
        )
        return TranscriptionResult(
            text=text.strip(),
            language=language,
            segments=segments or [TranscriptSegment(start_seconds=0.0, end_seconds=0.0, text=text.strip())],
        )

    def _create_client(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise TranscriptionError(
                "The openai-api backend requires the 'openai' package. "
                "Install it with: pip install transcribee[openai-api]"
            )
        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return OpenAI(**kwargs)
