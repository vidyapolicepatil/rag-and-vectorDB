import numpy as np
import pytest

from app.config import Settings
from app.errors import ServiceError
from app.services.document_service import TextChunk
from app.services.vector_store import VectorStore


def test_chroma_index_persists_and_uses_cosine_similarity(tmp_path):
    settings = Settings(data_directory=tmp_path)
    chunk = TextChunk("chunk-1", "A retrieval passage.", None)
    first_store = VectorStore(settings)

    first_store.add(
        "chroma",
        "doc-test123",
        [chunk],
        np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
        document_id="document-1",
        filename="notes.txt",
    )

    second_store = VectorStore(settings)
    results = second_store.search(
        "chroma",
        "doc-test123",
        np.asarray([1.0, 0.0, 0.0], dtype=np.float32),
        top_k=5,
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-1"
    assert results[0]["filename"] == "notes.txt"
    assert results[0]["relevance_score"] == 1.0

    second_store.delete("chroma", "doc-test123")


def test_faiss_index_persists_metadata_and_uses_cosine_similarity(tmp_path):
    pytest.importorskip("faiss")
    settings = Settings(data_directory=tmp_path)
    chunk = TextChunk("chunk-1", "A retrieval passage.", None)

    VectorStore(settings).add(
        "faiss",
        "doc-test123",
        [chunk],
        np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
        document_id="document-1",
        filename="notes.txt",
    )

    results = VectorStore(settings).search(
        "faiss",
        "doc-test123",
        np.asarray([1.0, 0.0, 0.0], dtype=np.float32),
        top_k=5,
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-1"
    assert results[0]["filename"] == "notes.txt"
    assert results[0]["relevance_score"] == 1.0
    VectorStore(settings).delete("faiss", "doc-test123")


def test_chroma_dimension_error_is_reported_with_retrieval_context(tmp_path):
    settings = Settings(data_directory=tmp_path)
    store = VectorStore(settings)
    store.add(
        "chroma",
        "doc-dimension",
        [TextChunk("chunk-1", "A retrieval passage.", None)],
        np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
        document_id="document-1",
        filename="notes.txt",
    )

    with pytest.raises(ServiceError, match="ChromaDB retrieval failed"):
        store.search(
            "chroma",
            "doc-dimension",
            np.asarray([1.0, 0.0], dtype=np.float32),
            top_k=5,
        )
    store.delete("chroma", "doc-dimension")
