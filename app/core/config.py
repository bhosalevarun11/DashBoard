from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app_name: str = "Dashboard Analytics"
    app_env: str = "development"
    secret_key: str = "dev-secret-change-in-production"
    encryption_key: str = "dev-encryption-key-change-me!!"

    database_url: str = "postgresql+asyncpg://postgres:varun11@127.0.0.1:5433/ecommerce_analytics"
    database_url_sync: str = "postgresql://postgres:varun11@127.0.0.1:5433/ecommerce_analytics"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    max_upload_size_mb: int = 50
    upload_dir: str = "uploads"
    frontend_url: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
