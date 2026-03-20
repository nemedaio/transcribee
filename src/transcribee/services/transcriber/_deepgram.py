from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from transcribee.config import Settings
from transcribee.logging import get_logger
from transcribee.services.transcriber._protocol import (
    TranscriptionError,
    TranscriptionResult,
    TranscriptSegment,
)

logger = get_logger(__name__)

_DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"


class DeepgramTranscriber:
    """Transcribes audio via the Deepgram API. Requires DEEPGRAM_API_KEY."""

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.deepgram_api_key
        self.model = settings.deepgram_model
        self.language = settings.deepgram_language
        if not self.api_key:
            raise TranscriptionError(
                "The deepgram backend requires DEEPGRAM_API_KEY to be set in your environment."
            )

    def transcribe(self, media_file_path: str) -> TranscriptionResult:
        logger.info(
            "transcriber.start path=%s model=%s backend=deepgram",
            media_file_path,
            self.model,
        )
        try:
            result = self._call_api(media_file_path)
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc

        channel = (
            result.get("results", {})
            .get("channels", [{}])[0]
        )
        alternative = channel.get("alternatives", [{}])[0]
        text = alternative.get("transcript", "")
        detected_language = channel.get("detected_language") or alternative.get("language")

        words = alternative.get("words", [])
        segments = self._words_to_segments(words)

        if not segments and text:
            segments = [TranscriptSegment(start_seconds=0.0, end_seconds=0.0, text=text.strip())]

        logger.info(
            "transcriber.complete path=%s language=%s segments=%s",
            media_file_path,
            detected_language,
            len(segments),
        )
        return TranscriptionResult(
            text=text.strip(),
            language=detected_language,
            segments=segments,
        )

    def _call_api(self, media_file_path: str) -> dict:
        params = {
            "model": self.model,
            "smart_format": "true",
            "utterances": "true",
            "detect_language": "true" if not self.language else "false",
        }
        if self.language:
            params["language"] = self.language

        url = f"{_DEEPGRAM_API_URL}?{urlencode(params)}"
        audio_path = Path(media_file_path)
        suffix = audio_path.suffix.lstrip(".")
        content_type = f"audio/{suffix}" if suffix else "audio/wav"

        with open(media_file_path, "rb") as f:
            audio_data = f.read()

        request = Request(
            url,
            data=audio_data,
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type": content_type,
            },
            method="POST",
        )
        with urlopen(request) as response:
            return json.loads(response.read())

    @staticmethod
    def _words_to_segments(words: list[dict], max_gap: float = 1.0) -> list[TranscriptSegment]:
        if not words:
            return []
        segments: list[TranscriptSegment] = []
        current_start = words[0].get("start", 0.0)
        current_texts: list[str] = [words[0].get("word", "")]

        for prev, word in zip(words, words[1:]):
            gap = word.get("start", 0.0) - prev.get("end", 0.0)
            if gap > max_gap:
                segments.append(TranscriptSegment(
                    start_seconds=current_start,
                    end_seconds=prev.get("end", 0.0),
                    text=" ".join(current_texts).strip(),
                ))
                current_start = word.get("start", 0.0)
                current_texts = []
            current_texts.append(word.get("word", ""))

        segments.append(TranscriptSegment(
            start_seconds=current_start,
            end_seconds=words[-1].get("end", 0.0),
            text=" ".join(current_texts).strip(),
        ))
        return segments
