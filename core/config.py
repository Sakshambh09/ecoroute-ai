"""Typed application configuration via pydantic-settings.

All environment variables are validated at startup; a misconfigured
environment fails fast with a clear error instead of misbehaving at runtime.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Security
    api_keys: str = ""  # comma-separated; empty disables auth (dev mode)
    rate_limit_per_minute: int = 60

    # Inference
    inference_provider: str = Field(default="heuristic", pattern="^(heuristic|kompact)$")

    # RAG
    embedding_model: str = "all-MiniLM-L6-v2"
    rag_top_k: int = 3
    index_path: Path = BASE_DIR / "data" / "index.faiss"
    chunks_path: Path = BASE_DIR / "data" / "chunks.json"
    documents_path: Path = BASE_DIR / "data" / "documents.json"

    # Persistent impact ledger
    ledger_path: Path = BASE_DIR / "data" / "ledger.db"

    # Logging
    log_level: str = "INFO"

    # Cost comparison baselines
    cloud_llm_cost_per_1m_tokens_usd: float = 0.50
    cpu_energy_cost_per_kwh_inr: float = 9.0

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def auth_enabled(self) -> bool:
        return len(self.api_key_list) > 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
