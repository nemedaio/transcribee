"""Tests for the pluggable transcriber backend factory and error handling."""
import pytest

from transcribee.config import Settings
from transcribee.services.transcriber import create_transcriber, TranscriptionError
from transcribee.services.transcriber._factory import _BACKENDS


def _settings(**overrides) -> Settings:
    base = dict(
        data_dir="/tmp/test",
        database_url="sqlite:///",
        transcriber_backend="faster-whisper",
    )
    base.update(overrides)
    return Settings(**base)


def test_factory_returns_faster_whisper_by_default():
    from transcribee.services.transcriber._faster_whisper import FasterWhisperTranscriber

    transcriber = create_transcriber(_settings())

    assert isinstance(transcriber, FasterWhisperTranscriber)


def test_factory_returns_openai_whisper_backend():
    from transcribee.services.transcriber._openai_whisper import OpenAIWhisperTranscriber

    transcriber = create_transcriber(_settings(transcriber_backend="openai-whisper"))

    assert isinstance(transcriber, OpenAIWhisperTranscriber)


def test_factory_returns_whisper_cpp_backend():
    from transcribee.services.transcriber._whisper_cpp import WhisperCppTranscriber

    transcriber = create_transcriber(_settings(transcriber_backend="whisper-cpp"))

    assert isinstance(transcriber, WhisperCppTranscriber)


def test_factory_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unknown transcriber backend: 'does-not-exist'"):
        create_transcriber(_settings(transcriber_backend="does-not-exist"))


def test_factory_error_lists_supported_backends():
    with pytest.raises(ValueError, match="deepgram") as exc_info:
        create_transcriber(_settings(transcriber_backend="nope"))

    message = str(exc_info.value)
    for backend in _BACKENDS:
        assert backend in message


def test_openai_api_backend_requires_api_key():
    with pytest.raises(TranscriptionError, match="OPENAI_API_KEY"):
        create_transcriber(_settings(transcriber_backend="openai-api"))


def test_openai_api_backend_accepts_api_key():
    from transcribee.services.transcriber._openai_api import OpenAIApiTranscriber

    transcriber = create_transcriber(_settings(
        transcriber_backend="openai-api",
        openai_api_key="sk-test-key",
    ))

    assert isinstance(transcriber, OpenAIApiTranscriber)


def test_openai_api_backend_accepts_custom_base_url():
    from transcribee.services.transcriber._openai_api import OpenAIApiTranscriber

    transcriber = create_transcriber(_settings(
        transcriber_backend="openai-api",
        openai_api_key="sk-test-key",
        openai_api_base_url="https://custom.api.example.com/v1",
    ))

    assert isinstance(transcriber, OpenAIApiTranscriber)
    assert transcriber.base_url == "https://custom.api.example.com/v1"


def test_deepgram_backend_requires_api_key():
    with pytest.raises(TranscriptionError, match="DEEPGRAM_API_KEY"):
        create_transcriber(_settings(transcriber_backend="deepgram"))


def test_deepgram_backend_accepts_api_key():
    from transcribee.services.transcriber._deepgram import DeepgramTranscriber

    transcriber = create_transcriber(_settings(
        transcriber_backend="deepgram",
        deepgram_api_key="dg-test-key",
    ))

    assert isinstance(transcriber, DeepgramTranscriber)


def test_faster_whisper_passes_model_settings():
    transcriber = create_transcriber(_settings(
        whisper_model="tiny",
        whisper_device="cpu",
        whisper_compute_type="int8",
    ))

    assert transcriber.model_name == "tiny"
    assert transcriber.device == "cpu"
    assert transcriber.compute_type == "int8"


def test_all_registered_backends_are_importable():
    for backend_name in _BACKENDS:
        settings_kwargs = dict(transcriber_backend=backend_name)
        if backend_name == "openai-api":
            settings_kwargs["openai_api_key"] = "sk-test"
        elif backend_name == "deepgram":
            settings_kwargs["deepgram_api_key"] = "dg-test"
        transcriber = create_transcriber(_settings(**settings_kwargs))
        assert hasattr(transcriber, "transcribe")
