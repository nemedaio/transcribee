from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LinkedIn Transcript App"
    environment: str = "development"
    data_dir: str = "./data"
    media_dir: str | None = None
    database_url: str | None = None
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
