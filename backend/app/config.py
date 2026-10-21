from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    embedding_model: Literal["sentence-transformers/all-MiniLM-L6-v2"] = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    chunk_size: int = Field(default=800, gt=0, le=10000)
    chunk_overlap: int = Field(default=160, ge=0, le=9999)
    top_k: Literal[5] = 5
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    data_directory: Path = BACKEND_ROOT / "data"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE.")
        return self

    @property
    def uploads_directory(self) -> Path:
        return self.data_directory / "uploads"

    @property
    def chroma_directory(self) -> Path:
        return self.data_directory / "chroma_db"

    @property
    def faiss_directory(self) -> Path:
        return self.data_directory / "faiss_index"

    @property
    def experiment_directory(self) -> Path:
        return self.data_directory / "experiments"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for directory in (
        settings.uploads_directory,
        settings.chroma_directory,
        settings.faiss_directory,
        settings.experiment_directory,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return settings
