from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "University Service"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://uni:uni@localhost:5432/uni_service"
    ALEMBIC_DATABASE_URL: str = (
        "postgresql+psycopg2://uni:uni@localhost:5432/uni_service"
    )

    # Development-only fallback. Production startup must reject it.
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, gt=0)

    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    NVIDIA_TIMEOUT_SECONDS: float = Field(default=30, gt=0, le=120)
    NVIDIA_MAX_RETRIES: int = Field(default=2, ge=0, le=3)
    AI_PROCESSING_CONCURRENCY: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def check_production_security(self):
        if self.ENVIRONMENT == "production":
            weak_values = {
                "", "change-me-in-production", "changeme", "secret",
                "your-secret-key", "replace-me", "test-secret",
            }
            secret = self.JWT_SECRET.strip()
            if len(secret) < 32 or secret.lower() in weak_values or len(set(secret)) < 8:
                raise ValueError(
                    "Production requires a non-template JWT_SECRET of at least 32 characters"
                )
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
