from transcribee.config import Settings
from transcribee.logging import get_logger
from transcribee.services.transcriber._protocol import (
    TranscriptionError,
    TranscriptionResult,
    TranscriptSegment,
)

logger = get_logger(__name__)


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings) -> None:
        self.model_name = settings.whisper_model
        self.device = settings.whisper_device
        self.compute_type = settings.whisper_compute_type
        self._model = None

    def transcribe(self, media_file_path: str) -> TranscriptionResult:
        logger.info("transcriber.start path=%s model=%s backend=faster-whisper", media_file_path, self.model_name)
        try:
            model = self._load_model()
            segments, info = model.transcribe(media_file_path)
            collected_segments = [
                TranscriptSegment(
                    start_seconds=segment.start,
                    end_seconds=segment.end,
                    text=segment.text.strip(),
                )
                for segment in segments
            ]
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc

        transcript_text = " ".join(segment.text for segment in collected_segments if segment.text).strip()
        logger.info(
            "transcriber.complete path=%s language=%s segments=%s",
            media_file_path,
            getattr(info, "language", None),
            len(collected_segments),
        )
        return TranscriptionResult(
            text=transcript_text,
            language=getattr(info, "language", None),
            segments=collected_segments,
        )

    def _load_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise TranscriptionError(
                    "The faster-whisper backend requires the 'faster-whisper' package. "
                    "Install it with: pip install transcribee[faster-whisper]"
                )
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info(
                "transcriber.model_loaded model=%s device=%s compute_type=%s",
                self.model_name,
                self.device,
                self.compute_type,
            )
        return self._model
