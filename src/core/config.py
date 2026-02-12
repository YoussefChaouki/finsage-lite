"""
Application Configuration

Centralized settings management using Pydantic BaseSettings.
All values are loaded from environment variables or .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable binding.

    Required env vars (no defaults):
        POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB

    Optional env vars:
        POSTGRES_PORT (5432), LOG_LEVEL (INFO), OLLAMA_BASE_URL,
        OLLAMA_MODEL (mistral), EDGAR_USER_AGENT
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

    # Chunking
    CHUNK_SIZE: int = 250
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",  # Silently ignore unknown env vars
    )

    @property
    def DATABASE_URL(self) -> str:
        """Async PostgreSQL connection string using asyncpg driver."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()  # type: ignore[call-arg]
