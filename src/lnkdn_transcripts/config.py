from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LinkedIn Transcript App"
    environment: str = "development"
    data_dir: str = "./data"
    whisper_model: str = "base"
    max_upload_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
