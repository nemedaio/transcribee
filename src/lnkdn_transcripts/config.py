from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LinkedIn Transcript App"
    environment: str = "development"
    data_dir: str = "./data"
    media_dir: str | None = None
    database_url: str | None = None
    auth_enabled: bool = False
    auth_test_mode: bool = False
    session_secret_key: str | None = None
    session_cookie_name: str = "lnkdn_transcripts_session"
    session_https_only: bool = False
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_allowed_email_domains: str | None = None
    extracted_audio_format: str = "wav"
    extracted_audio_sample_rate: int = 16000
    extracted_audio_channels: int = 1
    retain_source_media: bool = False
    artifact_retention_days: int = 7
    whisper_model: str = "base"
    whisper_device: str = "auto"
    whisper_compute_type: str = "default"
    max_upload_minutes: int = 30
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
