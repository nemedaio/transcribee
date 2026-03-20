from transcribee.config import Settings
from transcribee.logging import get_logger
from transcribee.services.transcriber._protocol import (
    TranscriptionError,
    TranscriptionResult,
    TranscriptSegment,
)

logger = get_logger(__name__)


class OpenAIWhisperTranscriber:
    def __init__(self, settings: Settings) -> None:
        self.model_name = settings.whisper_model
        self.device = settings.whisper_device
        self._model = None

    def transcribe(self, media_file_path: str) -> TranscriptionResult:
        logger.info("transcriber.start path=%s model=%s backend=openai-whisper", media_file_path, self.model_name)
        try:
            model = self._load_model()
            result = model.transcribe(media_file_path)
            collected_segments = [
                TranscriptSegment(
                    start_seconds=seg["start"],
                    end_seconds=seg["end"],
                    text=seg["text"].strip(),
                )
                for seg in result.get("segments", [])
            ]
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc

        transcript_text = " ".join(s.text for s in collected_segments if s.text).strip()
        language = result.get("language")
        logger.info(
            "transcriber.complete path=%s language=%s segments=%s",
            media_file_path,
            language,
            len(collected_segments),
        )
        return TranscriptionResult(
            text=transcript_text,
            language=language,
            segments=collected_segments,
        )

    def _load_model(self):
        if self._model is None:
            try:
                import whisper
            except ImportError:
                raise TranscriptionError(
                    "The openai-whisper backend requires the 'openai-whisper' package. "
                    "Install it with: pip install transcribee[openai-whisper]"
                )
            self._model = whisper.load_model(self.model_name, device=self.device)
            logger.info(
                "transcriber.model_loaded model=%s device=%s",
                self.model_name,
                self.device,
            )
        return self._model
