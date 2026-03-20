import importlib

from transcribee.config import Settings
from transcribee.logging import get_logger
from transcribee.services.transcriber._protocol import MediaTranscriber

logger = get_logger(__name__)

_BACKENDS: dict[str, str] = {
    # Local backends (free, no API key needed)
    "faster-whisper": "transcribee.services.transcriber._faster_whisper.FasterWhisperTranscriber",
    "openai-whisper": "transcribee.services.transcriber._openai_whisper.OpenAIWhisperTranscriber",
    "whisper-cpp": "transcribee.services.transcriber._whisper_cpp.WhisperCppTranscriber",
    # Cloud API backends (bring your own key)
    "openai-api": "transcribee.services.transcriber._openai_api.OpenAIApiTranscriber",
    "deepgram": "transcribee.services.transcriber._deepgram.DeepgramTranscriber",
}


def create_transcriber(settings: Settings) -> MediaTranscriber:
    backend = settings.transcriber_backend
    dotted_path = _BACKENDS.get(backend)
    if dotted_path is None:
        raise ValueError(
            f"Unknown transcriber backend: {backend!r}. "
            f"Supported backends: {', '.join(sorted(_BACKENDS))}"
        )
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    logger.info("transcriber.factory backend=%s", backend)
    return cls(settings)
