from transcribee.config import Settings
from transcribee.logging import get_logger
from transcribee.services.transcriber._protocol import (
    TranscriptionError,
    TranscriptionResult,
    TranscriptSegment,
)

logger = get_logger(__name__)


class WhisperCppTranscriber:
    def __init__(self, settings: Settings) -> None:
        self.model_name = settings.whisper_model
        self._model = None

    def transcribe(self, media_file_path: str) -> TranscriptionResult:
        logger.info("transcriber.start path=%s model=%s backend=whisper-cpp", media_file_path, self.model_name)
        try:
            model = self._load_model()
            segments_raw = model.transcribe(media_file_path)
            collected_segments = [
                TranscriptSegment(
                    start_seconds=seg.t0 / 100.0,
                    end_seconds=seg.t1 / 100.0,
                    text=seg.text.strip(),
                )
                for seg in segments_raw
            ]
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc

        transcript_text = " ".join(s.text for s in collected_segments if s.text).strip()
        logger.info(
            "transcriber.complete path=%s segments=%s",
            media_file_path,
            len(collected_segments),
        )
        return TranscriptionResult(
            text=transcript_text,
            language=None,
            segments=collected_segments,
        )

    def _load_model(self):
        if self._model is None:
            try:
                from pywhispercpp.model import Model
            except ImportError:
                raise TranscriptionError(
                    "The whisper-cpp backend requires the 'pywhispercpp' package. "
                    "Install it with: pip install transcribee[whisper-cpp]"
                )
            self._model = Model(self.model_name)
            logger.info("transcriber.model_loaded model=%s", self.model_name)
        return self._model
