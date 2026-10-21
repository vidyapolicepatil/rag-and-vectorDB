def test_generate_rejects_empty_question(client):
    response = client.post("/api/generate", json={"question": "   "})

    assert response.status_code == 422


def test_generate_returns_sources_and_retrieval_timings(client, uploaded_document):
    response = client.post(
        "/api/generate",
        json={
            "question": "What do retrieval systems find?",
            "document_id": uploaded_document["document_id"],
            "vector_database": "chroma",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["answer"] == "The sample document describes a retrieval system."
    assert result["sources"]
    assert result["sources"][0]["filename"] == "research.txt"
    assert result["sources"][0]["chunk_id"]
    assert result["timings"]["retrieval_ms"] >= 0
    assert client.app.state.test_services.groq.last_question == "What do retrieval systems find?"


def test_generate_does_not_write_chat_history(client, uploaded_document):
    history_path = client.app.state.test_services.documents.settings.data_directory / "history.db"
    sentinel = b"existing history data must remain untouched"
    history_path.write_bytes(sentinel)

    response = client.post(
        "/api/generate",
        json={
            "question": "What do retrieval systems find?",
            "document_id": uploaded_document["document_id"],
        },
    )

    assert response.status_code == 200
    assert history_path.read_bytes() == sentinel
    assert client.get("/history").status_code == 404


def test_generate_rejects_unknown_vector_database(client):
    response = client.post(
        "/api/generate",
        json={"question": "What is this?", "vector_database": "unknown"},
    )

    assert response.status_code == 422


def test_generate_without_available_documents_returns_clear_error(client):
    response = client.post("/api/generate", json={"question": "What is in the document?"})

    assert response.status_code == 404
    assert "No documents" in response.json()["detail"]


def test_groq_requires_server_side_api_key(tmp_path):
    import pytest

    from app.config import Settings
    from app.errors import ServiceError
    from app.services.groq_service import GroqService

    service = GroqService(Settings(data_directory=tmp_path, groq_api_key=None))

    with pytest.raises(ServiceError, match="GROQ_API_KEY"):
        service.generate_answer(
            "Question?",
            [{"chunk_id": "chunk-1", "filename": "notes.txt", "content": "Evidence", "page_number": None}],
        )
