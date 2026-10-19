from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_TRUTHY = {"1", "true", "t", "yes", "y", "on", "debug", "dev", "development"}
_FALSY = {"0", "false", "f", "no", "n", "off", "release", "prod", "production"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "uni-personal"
    app_env: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg2://uni:uni@localhost:5432/uni_personal"
    # Sync (psycopg2) URL used by Alembic migrations.
    alembic_database_url: str | None = None

    secret_key: str = "change-me-to-a-long-random-string"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value: object) -> object:
        """Be lenient: environments often set DEBUG to a non-boolean string."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _TRUTHY:
                return True
            if normalized in _FALSY:
                return False
        return value

    @property
    def sqlalchemy_database_url(self) -> str:
        """URL used for running migrations (falls back to the main DB URL)."""
        return self.alembic_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
