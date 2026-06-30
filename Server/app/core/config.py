from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"

    # Database
    database_url: str = "postgresql+psycopg2://voxintel:voxintel@localhost:5432/voxintel"

    # Auth
    jwt_secret_key: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24

    # Rate limiting (auth endpoints)
    auth_rate_limit_max_attempts: int = 10
    auth_rate_limit_window_seconds: int = 60

    # Object storage (MinIO / S3-compatible)
    storage_endpoint_url: str = "http://localhost:9000"
    storage_access_key: str = "voxintel"
    storage_secret_key: str = "voxintel123"
    storage_bucket: str = "voxintel-meetings"
    storage_region: str = "us-east-1"
    storage_secure: bool = False

    # Upload limits
    max_upload_size_bytes: int = 500 * 1024 * 1024  # 500 MB

    # Background processing (Celery + Redis)
    redis_url: str = "redis://localhost:6379/0"

    # Speech-to-text (worker-only; harmless for the API process to know about)
    whisper_model_size: str = "base"

    # Speaker diarization (worker-only). Set DIARIZATION_ENABLED=false to skip
    # diarization entirely and chain straight to summarization -- useful when
    # the worker doesn't have enough RAM for pyannote (~1.5 GB needed).
    # Transcription and AI summaries still work; speaker labels won't appear.
    diarization_enabled: bool = True
    hf_token: str = ""
    pyannote_pipeline_name: str = "pyannote/speaker-diarization-3.1"

    # AI summaries (worker-only). Generate a key at
    # https://console.anthropic.com/settings/keys. Without it, transcription
    # and diarization still work fine -- summarization just fails with a
    # clear "ANTHROPIC_API_KEY is not set" error instead of a summary.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
