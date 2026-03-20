from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Transcribee"
    environment: str = "development"
    data_dir: str = "./data"
    media_dir: str | None = None
    database_url: str | None = None
    auth_enabled: bool = False
    auth_test_mode: bool = False
    session_secret_key: str | None = None
    session_cookie_name: str = "transcribee_session"
    session_https_only: bool = False
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_allowed_email_domains: str | None = None
    google_allowed_emails: str | None = None
    google_admin_emails: str | None = None
    google_require_approval: bool = False
    access_audit_retention_days: int = 90
    extracted_audio_format: str = "wav"
    extracted_audio_sample_rate: int = 16000
    extracted_audio_channels: int = 1
    retain_source_media: bool = False
    artifact_retention_days: int = 7
    transcriber_backend: str = "faster-whisper"
    whisper_model: str = "large-v3-turbo"
    whisper_device: str = "auto"
    whisper_compute_type: str = "default"
    openai_api_key: str | None = None
    openai_api_base_url: str | None = None
    openai_whisper_model: str = "whisper-1"
    deepgram_api_key: str | None = None
    deepgram_model: str = "nova-3"
    deepgram_language: str | None = None
    max_upload_minutes: int = 30
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
