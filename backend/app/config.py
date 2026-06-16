"""
Application configuration using pydantic-settings.
All values can be overridden via environment variables.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Investigation Intelligence Platform"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://iip_user:iip_secret_2024@localhost:5432/investigation_db"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://:iip_redis_2024@localhost:6379/0"
    redis_ttl_seconds: int = 3600

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "iip_minio"
    minio_secret_key: str = "iip_minio_secret_2024"
    minio_bucket_name: str = "investigation-evidence"
    minio_secure: bool = False

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_token: str = "iip_chroma_token"
    chroma_collection: str = "investigation_evidence"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_timeout: int = 300

    # JWT
    jwt_secret_key: str = "super_secret_jwt_key_change_in_prod_2024"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # AI/ML
    spacy_model: str = "en_core_web_sm"
    sentence_transformer_model: str = "all-MiniLM-L6-v2"

    # File upload
    max_file_size_mb: int = 500
    allowed_extensions: list[str] = [
        ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff",
        ".mp4", ".avi", ".mov", ".mkv",
        ".txt", ".docx", ".doc", ".csv",
        ".json", ".xml",
    ]

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @property
    def sync_database_url(self) -> str:
        """Synchronous DB URL for Alembic and Celery."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
