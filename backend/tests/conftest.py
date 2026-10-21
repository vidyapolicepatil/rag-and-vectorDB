from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_services
from app.main import create_app
from app.services.document_service import DocumentService
from app.services.experiment_service import ExperimentService
from app.services.retrieval_service import RetrievalService


class FakeEmbeddings:
    def embed(self, texts: list[str]) -> np.ndarray:
        return np.full((len(texts), 384), 1 / np.sqrt(384), dtype=np.float32)


class FakeVectorStore:
    def __init__(self) -> None:
        self.indexes: dict[tuple[str, str], list[dict[str, object]]] = {}

    @staticmethod
    def faiss_available() -> bool:
        return False

    def add(self, vector_database, index_key, chunks, vectors, document_id, filename) -> None:
        self.indexes[(vector_database, index_key)] = [
            {
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "document_id": document_id,
                "filename": filename,
                "page_number": chunk.page_number,
                "relevance_score": 0.75,
            }
            for chunk in chunks
        ]

    def search(self, vector_database, index_key, query_vector, top_k):
        return self.indexes.get((vector_database, index_key), [])[:top_k]

    def delete(self, vector_database, index_key) -> None:
        self.indexes.pop((vector_database, index_key), None)


class FakeGroqService:
    def __init__(self) -> None:
        self.last_question = None

    def generate_answer(self, question, context):
        self.last_question = question
        return "The sample document describes a retrieval system."


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(data_directory=tmp_path)
    embeddings = FakeEmbeddings()
    vector_store = FakeVectorStore()
    documents = DocumentService(settings, embeddings, vector_store)
    groq = FakeGroqService()
    services = SimpleNamespace(
        documents=documents,
        embeddings=embeddings,
        vector_store=vector_store,
        retrieval=RetrievalService(settings, documents, embeddings, vector_store),
        groq=groq,
        experiments=ExperimentService(settings, documents, embeddings, vector_store),
    )
    application = create_app(settings)
    application.dependency_overrides[get_services] = lambda: services
    with TestClient(application) as test_client:
        test_client.app.state.test_services = services
        yield test_client
    application.dependency_overrides.clear()


@pytest.fixture
def uploaded_document(client):
    response = client.post(
        "/api/upload",
        files={"file": ("research.txt", b"Retrieval systems find useful text. " * 20, "text/plain")},
    )
    assert response.status_code == 201
    return response.json()


def make_experiment_payload(document_id: str, **overrides):
    payload = {
        "document_id": document_id,
        "chunk_sizes": [200, 400, 600, 800, 1000],
        "overlap_percent": 20,
        "top_k": 5,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_approaches": ["chroma", "faiss"],
        "questions": ["What do retrieval systems find?"],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def experiment_payload(uploaded_document):
    return make_experiment_payload(uploaded_document["document_id"])


@pytest.fixture
def unused_id():
    return str(uuid4())
