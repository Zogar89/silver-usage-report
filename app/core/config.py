from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Silver Usage Report"
    app_base_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./silver_usage_report.db"
    secret_key: str = "dev-secret-change-me"
    admin_token: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
