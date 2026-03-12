from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LinkedIn Transcript App"
    environment: str = "development"
    data_dir: str = "./data"
    media_dir: str | None = None
    database_url: str | None = None
    whisper_model: str = "base"
    max_upload_minutes: int = 30
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
