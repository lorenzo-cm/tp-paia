from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application settings
    PROJECT_NAME: str = "Projeto de PAIA"
    VERSION: str = "1.0.0"
    API_PREFIX: str = ""

    # .env config
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod"),
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: Literal["local", "staging", "prod"] = "local"

    # JWT config
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    ALGORITHM: str = "HS256"
    SECRET_KEY: str
    JWT_SECRET_KEY: str  # openssl rand -hex 32 or secrets.token_urlsafe(32)

    # Database settings
    DATABASE_URL: PostgresDsn

    # R2 settings
    R2_ENDPOINT_URL: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    R2_PUB_URL: str
    
    # Chatwoot settings
    CHATWOOT_API_URL: str
    CHATWOOT_API_KEY: str
    CHATWOOT_ACCOUNT_ID: int
    
    # Redis settings
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    
    # Debounce settings
    DEBOUNCE_WAIT_TIME: int = 5000      # in milliseconds
    DEBOUNCE_MAX_ATTEMPTS: int = 10     # max number of attempts to send a message
    DEBOUNCE_MAX_MESSAGES: int = 10     # cap of buffered payloads consumed per burst

    # Transcription
    TRANSCRIPTION_PROVIDER: Literal["openai", "elevenlabs"] = "openai"

    OPENAI_API_KEY: str | None = None
    OPENAI_TRANSCRIPTION_MODEL: str = "gpt-4o-transcribe"

    ELEVENLABS_API_KEY: str | None = None
    ELEVENLABS_TRANSCRIPTION_MODEL: str = "scribe_v2"

    # Agent (LLM)
    AGENT_PROVIDER: Literal["openai", "anthropic"] = "openai"
    ANTHROPIC_API_KEY: str | None = None
    AGENT_HISTORY_LIMIT: int = 20  # recent messages fed to the agent as history

    # Real estate RAG / Qdrant
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "buildings_rag"
    QDRANT_EMBEDDING_MODEL: str = "text-embedding-3-small"
    QDRANT_VECTOR_SIZE: int = 1536
    QDRANT_SEARCH_LIMIT: int = 5
    RAG_DENSE_WEIGHT: float = 0.7
    RAG_BM25_WEIGHT: float = 0.3
    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 160
    RAG_MAX_CONTEXT_CHUNKS: int = 4

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Attachments
    MAX_ATTACHMENT_BYTES: int = 25 * 1024 * 1024  # 25 MiB

    # Document extraction (Fase 2 — see Obsidian task chatwoot webhook pipeline)
    # `None` (omitted from .env) and `"disabled"` both mean "processor off".
    DOCUMENT_PROCESSOR_TYPE: Literal["docling_local", "docling_modal", "disabled"] | None = (
        "docling_local"
    )
    
    MAX_DOCUMENT_BYTES: int = 50 * 1024 * 1024  # 50 MiB

    # NSFW moderation (Phase 01 — see Obsidian task nsfw_moderation)
    # `None` (omitted from .env) and `""` both mean "moderation off".
    NSFW_PROVIDER: Literal["openai_moderation"] | None = "openai_moderation"

    @field_validator("NSFW_PROVIDER", mode="before")
    @classmethod
    def _empty_nsfw_provider_is_none(cls, v: object) -> object:
        if isinstance(v, str) and v == "":
            return None
        return v

    # Modal docling
    MODAL_APP_NAME: str = "template-document-processor"
    MODAL_FUNCTION_NAME: str = "extract_markdown"
    MODAL_TOKEN_ID: str | None = None
    MODAL_TOKEN_SECRET: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
