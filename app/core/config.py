from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "University Service"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://uni:uni@localhost:5432/uni_service"
    ALEMBIC_DATABASE_URL: str = "postgresql+psycopg2://uni:uni@localhost:5432/uni_service"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
