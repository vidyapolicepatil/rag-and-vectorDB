import logging
import time

import numpy as np

from app.config import Settings
from app.errors import ServiceError
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        documents: DocumentService,
        embeddings: EmbeddingService,
        vector_store,
    ) -> None:
        self.settings = settings
        self.documents = documents
        self.embeddings = embeddings
        self.vector_store = vector_store

    def retrieve(
        self,
        question: str,
        vector_database: str,
        document_id: str | None = None,
    ) -> tuple[list[dict[str, object]], float, float]:
        if not question.strip():
            raise ServiceError(422, "Question must not be empty.")
        ids = [document_id] if document_id else self.documents.document_ids()
        if not ids:
            raise ServiceError(404, "No documents are available. Upload a PDF or TXT file first.")
        for current_id in ids:
            self.documents.get_document(current_id)

        embedding_start = time.perf_counter()
        query_vector = self.embeddings.embed([question])[0]
        embedding_ms = (time.perf_counter() - embedding_start) * 1000

        retrieval_start = time.perf_counter()
        candidates: list[dict[str, object]] = []
        for current_id in ids:
            index_key = f"doc-{current_id.replace('-', '')}"
            candidates.extend(
                self.vector_store.search(
                    vector_database,
                    index_key,
                    np.asarray(query_vector, dtype=np.float32),
                    self.settings.top_k,
                )
            )
        candidates.sort(
            key=lambda item: float(item["relevance_score"]),
            reverse=True,
        )
        return candidates[: self.settings.top_k], embedding_ms, (time.perf_counter() - retrieval_start) * 1000
