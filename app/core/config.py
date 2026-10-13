from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "uni-personal"
    app_env: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg2://uni:uni@localhost:5432/uni_personal"

    secret_key: str = "change-me-to-a-long-random-string"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()
