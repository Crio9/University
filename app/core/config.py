from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "University Service"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://uni:uni@localhost:5432/uni_service"
    ALEMBIC_DATABASE_URL: str = (
        "postgresql+psycopg2://uni:uni@localhost:5432/uni_service"
    )

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    NVIDIA_TIMEOUT_SECONDS: float = Field(default=30, gt=0, le=120)
    NVIDIA_MAX_RETRIES: int = Field(default=2, ge=0, le=3)
    AI_PROCESSING_CONCURRENCY: int = Field(default=3, ge=1, le=10)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
