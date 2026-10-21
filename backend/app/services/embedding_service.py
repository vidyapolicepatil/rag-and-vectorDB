from threading import Lock

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import Settings
from app.errors import ServiceError


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: SentenceTransformer | None = None
        self._lock = Lock()

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        self._model = SentenceTransformer(self.settings.embedding_model)
                    except Exception as error:
                        raise ServiceError(
                            503,
                            "The embedding model is unavailable. Check the model download and backend logs.",
                        ) from error
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        try:
            vectors = self._get_model().encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except ServiceError:
            raise
        except Exception as error:
            raise ServiceError(503, "Text embedding failed. Check the backend model configuration.") from error
        return np.asarray(vectors, dtype=np.float32)
