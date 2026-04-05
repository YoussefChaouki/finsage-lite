"""
Application Configuration

Centralized settings management using Pydantic BaseSettings.
All values are loaded from environment variables or .env file.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_POSTGRES_PASSWORD = "finsage_password"


class Settings(BaseSettings):
    """
    Application settings with environment variable binding.

    Required env vars (no defaults):
        POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB

    Optional env vars:
        POSTGRES_PORT (5432), LOG_LEVEL (INFO), OLLAMA_BASE_URL,
        OLLAMA_MODEL (mistral), EDGAR_USER_AGENT, CORS_ORIGINS
    """

    PROJECT_NAME: str = "FinSage-Lite"

    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str

    # Ollama LLM
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"

    # SEC EDGAR API
    EDGAR_USER_AGENT: str = "FinSage-Lite (contact@example.com)"

    # Embedding Model
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 64

    # Chunking
    CHUNK_SIZE: int = (
        220  # ~35 tokens headroom for contextual prefix within MiniLM's 256-token window
    )
    CHUNK_OVERLAP: int = 50

    # Search
    BM25_K1: float = 1.5
    BM25_B: float = 0.75
    RRF_K: int = 60
    DEFAULT_TOP_K: int = 5

    # Parsing
    PARSING_TARGET_SECTIONS: list[str] = ["1", "1A", "7", "7A", "8"]

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS — restrict to your actual frontend domain(s) in production
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",  # Silently ignore unknown env vars
    )

    @field_validator("EDGAR_USER_AGENT")
    @classmethod
    def validate_edgar_user_agent(cls, v: str) -> str:
        """Enforce SEC requirement: User-Agent must contain a contact email."""
        if "@" not in v:
            raise ValueError(
                "EDGAR_USER_AGENT must contain an email address as required by SEC EDGAR. "
                'Example: "FinSage-Lite contact@example.com"'
            )
        return v

    @property
    def DATABASE_URL(self) -> str:
        """Async PostgreSQL connection string using asyncpg driver."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()  # type: ignore[call-arg]
