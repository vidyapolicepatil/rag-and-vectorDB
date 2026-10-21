import numpy as np

from app.schemas import ExperimentRunRequest, ExperimentRunResult
from pydantic import ValidationError


class SharedEmbeddings:
    def embed(self, texts: list[str]) -> np.ndarray:
        return np.full((len(texts), 384), 1 / np.sqrt(384), dtype=np.float32)


def test_default_experiment_configuration_uses_paired_fixed_settings(uploaded_document):
    configuration = ExperimentRunRequest(
        document_id=uploaded_document["document_id"],
        questions=["What is the document about?"],
    )

    assert configuration.chunk_sizes == [200, 400, 600, 800, 1000]
    assert configuration.overlap_percent == 20
    assert configuration.top_k == 5
    assert configuration.vector_approaches == ["chroma", "faiss"]


def test_legacy_run_status_requires_complete_measurements():
    run = ExperimentRunResult.model_validate({
        "chunk_size": 200,
        "overlap": 40,
        "chunk_count": 1,
        "vector_approach": "chroma",
        "question": "What does the paper say?",
        "indexing_time_ms": 1.0,
        "retrieval_latency_ms": 0.5,
        "retrieved_chunks": [{"chunk_id": "chunk-1", "content": "Relevant passage."}],
    })
    incomplete_run = ExperimentRunResult.model_validate({
        "chunk_size": 200,
        "overlap": 40,
        "chunk_count": 1,
        "vector_approach": "faiss",
        "question": "What does the paper say?",
        "indexing_time_ms": 1.0,
        "retrieval_latency_ms": None,
        "retrieved_chunks": [],
    })

    assert run.status == "completed"
    assert incomplete_run.status == "failed"


def test_experiment_rejects_non_five_top_k(unused_id):
    try:
        ExperimentRunRequest(
            document_id=unused_id,
            questions=["Question"],
            top_k=3,
        )
    except ValidationError as error:
        assert "top_k" in str(error)
    else:
        raise AssertionError("top_k other than 5 must be rejected")


def test_experiment_rejects_duplicate_chunk_sizes(unused_id):
    try:
        ExperimentRunRequest(
            document_id=unused_id,
            questions=["Question"],
            chunk_sizes=[200, 200, 600, 800, 1000],
        )
    except ValidationError as error:
        assert "200, 400, 600, 800, and 1000" in str(error)
    else:
        raise AssertionError("Duplicate chunk sizes must be rejected")


def test_experiment_rejects_unsupported_chunk_size(unused_id):
    try:
        ExperimentRunRequest(
            document_id=unused_id,
            questions=["Question"],
            chunk_sizes=[200, 300, 600, 800, 1000],
        )
    except ValidationError as error:
        assert "200, 400, 600, 800, and 1000" in str(error)
    else:
        raise AssertionError("Only the five supported chunk sizes may be selected")


def test_experiment_rejects_non_twenty_percent_overlap(unused_id):
    try:
        ExperimentRunRequest(
            document_id=unused_id,
            questions=["Question"],
            overlap_percent=10,
        )
    except ValidationError as error:
        assert "overlap_percent" in str(error)
    else:
        raise AssertionError("Experiment overlap must be fixed at 20 percent")


def test_experiment_requires_both_vector_approaches(unused_id):
    try:
        ExperimentRunRequest(
            document_id=unused_id,
            questions=["Question"],
            vector_approaches=["chroma", "chroma"],
        )
    except ValidationError as error:
        assert "ChromaDB and FAISS" in str(error)
    else:
        raise AssertionError("Both vector approaches must be required")


def test_run_records_actual_pairings_and_measured_fields(client, experiment_payload):
    response = client.post("/api/experiments/run", json=experiment_payload)

    assert response.status_code == 201
    result = response.json()
    assert len(result["runs"]) == 10
    assert {run["vector_approach"] for run in result["runs"]} == {"chroma", "faiss"}
    assert {
        (run["chunk_size"], run["overlap"])
        for run in result["runs"]
    } == {(200, 40), (400, 80), (600, 120), (800, 160), (1000, 200)}
    assert all(run["indexing_time_ms"] >= 0 for run in result["runs"])
    assert all(run["retrieval_latency_ms"] >= 0 for run in result["runs"])
    assert all(run["chunk_count"] > 0 for run in result["runs"])
    assert all(run["errors"] == [] for run in result["runs"])
    assert all(run["status"] == "completed" for run in result["runs"])
    assert all("retrieved_chunks" in run for run in result["runs"])
    assert client.get("/api/experiments").json()["results"][0]["experiment_id"] == result["experiment_id"]


def test_experiment_runs_real_chroma_and_faiss_indexes(tmp_path):
    import io
    import pytest

    from app.config import Settings
    from app.services.document_service import DocumentService
    from app.services.experiment_service import ExperimentService
    from app.services.retrieval_service import RetrievalService
    from app.services.vector_store import VectorStore

    pytest.importorskip("faiss")
    settings = Settings(data_directory=tmp_path)
    embeddings = SharedEmbeddings()
    vector_store = VectorStore(settings)
    documents = DocumentService(settings, embeddings, vector_store)
    document = documents.upload(
        io.BytesIO(b"Shared vector retrieval passage. " * 100),
        "comparison.txt",
    )
    service = ExperimentService(settings, documents, embeddings, vector_store)
    retrieval = RetrievalService(settings, documents, embeddings, vector_store)

    for approach in ("chroma", "faiss"):
        passages, _, latency_ms = retrieval.retrieve(
            "What does the passage describe?",
            approach,
            document.document_id,
        )
        assert passages
        assert len(passages) <= settings.top_k
        assert latency_ms >= 0
        assert passages[0]["filename"] == "comparison.txt"
        assert passages[0]["chunk_id"]

    result = service.run(
        ExperimentRunRequest(
            document_id=document.document_id,
            overlap_percent=20,
            questions=["What does the passage describe?"],
        )
    )

    assert len(result["runs"]) == 10
    assert {run["chunk_size"] for run in result["runs"]} == {200, 400, 600, 800, 1000}
    assert all(
        run["overlap"] == int(run["chunk_size"] * 0.2)
        for run in result["runs"]
    )
    chroma = [run for run in result["runs"] if run["vector_approach"] == "chroma"]
    faiss = [run for run in result["runs"] if run["vector_approach"] == "faiss"]
    assert all(
        next(item for item in chroma if item["chunk_size"] == size)["chunk_count"]
        == next(item for item in faiss if item["chunk_size"] == size)["chunk_count"]
        for size in {200, 400, 600, 800, 1000}
    )
    assert all(0 < len(run["retrieved_chunks"]) <= 5 for run in result["runs"])
    assert all(chunk["chunk_id"] for run in result["runs"] for chunk in run["retrieved_chunks"])
    assert all(
        chunk["similarity_score"] == pytest.approx(1.0, abs=1e-5)
        for run in result["runs"]
        for chunk in run["retrieved_chunks"]
    )
    assert all(not run["errors"] for run in result["runs"])


def test_manual_evaluations_are_marked_as_manual(client, experiment_payload):
    experiment_payload["questions"] = [
        "What do retrieval systems find?",
        "What is another finding?",
    ]
    response = client.post("/api/experiments/run", json=experiment_payload)
    result = response.json()
    experiment_id = result["experiment_id"]
    selected_run = result["runs"][0]
    chunk_id = selected_run["retrieved_chunks"][0]["chunk_id"]

    evaluation = client.post(
        f"/api/experiments/{experiment_id}/evaluations",
        json={
            "evaluations": [
                {
                    "chunk_id": chunk_id,
                    "chunk_size": selected_run["chunk_size"],
                    "question": selected_run["question"],
                    "relevance": "relevant",
                    "context_contains_answer": True,
                    "note": "Manually reviewed against the question.",
                }
            ]
        },
    )

    assert evaluation.status_code == 200
    saved = client.get("/api/experiments").json()["results"][0]
    matching = [
        chunk
        for run in saved["runs"]
        for chunk in run["retrieved_chunks"]
        if run["chunk_size"] == selected_run["chunk_size"]
        and run["question"] == selected_run["question"]
        if chunk["chunk_id"] == chunk_id
    ]
    assert matching
    assert all(chunk["evaluation_source"] == "manual_review" for chunk in matching)
    assert all(chunk["manual_relevance"] == "relevant" for chunk in matching)
    assert len(matching) == 2
    other_question_chunks = [
        chunk
        for run in saved["runs"]
        if run["question"] != selected_run["question"]
        for chunk in run["retrieved_chunks"]
        if chunk["chunk_id"] == chunk_id
    ]
    assert other_question_chunks
    assert all(chunk["manual_relevance"] is None for chunk in other_question_chunks)


def test_experiment_records_faiss_errors_without_losing_chroma_results(client, experiment_payload, monkeypatch):
    from app.errors import ServiceError

    vector_store = client.app.state.test_services.vector_store
    original_add = vector_store.add

    def fail_faiss(vector_database, *args, **kwargs):
        if vector_database == "faiss":
            raise ServiceError(503, "FAISS is unavailable.")
        return original_add(vector_database, *args, **kwargs)

    monkeypatch.setattr(vector_store, "add", fail_faiss)
    response = client.post("/api/experiments/run", json=experiment_payload)

    assert response.status_code == 201
    runs = response.json()["runs"]
    chroma_run = next(run for run in runs if run["vector_approach"] == "chroma")
    faiss_run = next(run for run in runs if run["vector_approach"] == "faiss")
    assert chroma_run["errors"] == []
    assert faiss_run["errors"] == ["FAISS is unavailable."]
    assert chroma_run["retrieved_chunks"]
    assert faiss_run["retrieved_chunks"] == []
    assert faiss_run["indexing_time_ms"] is None
    assert faiss_run["retrieval_latency_ms"] is None
    assert faiss_run["status"] == "failed"
    assert chroma_run["status"] == "completed"


def test_groq_sdk_is_mocked(client, monkeypatch):
    from unittest.mock import Mock

    from app.services.groq_service import GroqService
    from app.config import Settings

    completion = Mock()
    completion.choices = [Mock(message=Mock(content="Grounded response."))]
    groq_client = Mock()
    groq_client.chat.completions.create.return_value = completion
    monkeypatch.setattr("app.services.groq_service.Groq", lambda **kwargs: groq_client)

    service = GroqService(Settings(data_directory=client.app.state.services.documents.settings.data_directory, groq_api_key="test-key"))
    result = service.generate_answer(
        "What is stated?",
        [{"chunk_id": "chunk-1", "filename": "paper.txt", "content": "The paper describes retrieval.", "page_number": None}],
    )

    assert result == "Grounded response."
    groq_client.chat.completions.create.assert_called_once()
