from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMEX_", env_file=".env", extra="ignore")

    api_token: str = Field(min_length=1)
    embed_model: str = "Qwen/Qwen3-Embedding-0.6B"
    device: str = "auto"
    qdrant_mode: str = "embedded"
    qdrant_path: Path = Path("~/.memex-backend/qdrant")
    qdrant_url: str = "http://localhost:6333"
    collection: str = "memex"
    chunk_tokens: int = Field(default=512, gt=0)
    chunk_overlap: int = Field(default=64, ge=0)

    @model_validator(mode="after")
    def validate_settings(self):
        if self.qdrant_mode not in {"embedded", "server"}:
            raise ValueError("MEMEX_QDRANT_MODE must be 'embedded' or 'server'")
        if self.device not in {"auto", "cpu", "cuda", "mps"}:
            raise ValueError("MEMEX_DEVICE must be auto, cpu, cuda, or mps")
        if self.chunk_overlap >= self.chunk_tokens:
            raise ValueError("MEMEX_CHUNK_OVERLAP must be smaller than MEMEX_CHUNK_TOKENS")
        return self

    @property
    def resolved_qdrant_path(self) -> Path:
        return self.qdrant_path.expanduser()


@lru_cache
def get_settings() -> Settings:
    return Settings()
