from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database ---------------------------------------------------------------
    database_url: str | None = None
    postgres_user: str = "jobpulse"
    postgres_password: str = "jobpulse"
    postgres_db: str = "jobpulse"
    postgres_host: str = "localhost"
    postgres_port: int = 55432

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Source ----------------------------------------------------------------
    himalayas_feed_url: str = "https://himalayas.app/jobs/rss"
    himalayas_user_agent: str = (
        "JobPulse/1.0 (+https://github.com/jobpulse; job-ingestion-dashboard)"
    )
    himalayas_source_name: str = "Himalayas RSS"
    himalayas_source_type: str = "rss"

    # Fetcher / retry / rate limiting ----------------------------------------
    fetch_timeout_seconds: float = 20.0
    fetch_max_retries: int = 3
    fetch_base_backoff_seconds: float = 1.0
    fetch_max_backoff_seconds: float = 30.0
    fetch_max_retry_after_seconds: float = 60.0
    minimum_request_interval_seconds: float = 5.0

    # Anomaly detection -------------------------------------------------------
    min_valid_jobs_threshold: int = 1
    max_invalid_ratio: float = 0.5
    anomaly_min_total_entries: int = 10

    # API / app ---------------------------------------------------------------
    app_name: str = "JobPulse"
    app_version: str = "1.0.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5174,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()