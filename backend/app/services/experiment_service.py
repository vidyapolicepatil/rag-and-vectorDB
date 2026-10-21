import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from app.config import Settings
from app.errors import ServiceError
from app.schemas import ExperimentRunRequest, ManualChunkEvaluation
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class ExperimentService:
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
        self.results_directory = settings.experiment_directory
        self.results_directory.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _result_path(self, experiment_id: str) -> Path:
        try:
            parsed_id = uuid.UUID(experiment_id)
        except ValueError as error:
            raise ServiceError(404, "Experiment not found.") from error
        return self.results_directory / f"{parsed_id}.json"

    def _load_result(self, path: Path) -> dict[str, object]:
        try:
            with path.open("r", encoding="utf-8") as result_file:
                result = json.load(result_file)
        except (OSError, json.JSONDecodeError) as error:
            logger.exception("Unable to read an experiment result record.")
            raise ServiceError(500, "An experiment result record could not be read.") from error
        if not isinstance(result, dict):
            raise ServiceError(500, "An experiment result record has an invalid format.")
        return result

    def _save_result(self, result: dict[str, object]) -> None:
        path = self._result_path(str(result["experiment_id"]))
        temporary_path = path.with_suffix(".json.tmp")
        try:
            with temporary_path.open("w", encoding="utf-8") as result_file:
                json.dump(result, result_file, ensure_ascii=False, indent=2)
                result_file.flush()
                os.fsync(result_file.fileno())
            temporary_path.replace(path)
        except OSError as error:
            temporary_path.unlink(missing_ok=True)
            logger.exception("Unable to save an experiment result record.")
            raise ServiceError(500, "Experiment results could not be saved.") from error

    def list_results(self) -> list[dict[str, object]]:
        results = []
        for path in sorted(self.results_directory.glob("*.json")):
            results.append(self._load_result(path))
        return results

    def run(self, request: ExperimentRunRequest) -> dict[str, object]:
        document = self.documents.get_document(request.document_id)
        document_path = self.documents.get_document_path(request.document_id)
        experiment_id = str(uuid.uuid4())
        result_runs: list[dict[str, object]] = []
        settings_snapshot = {
            "document_id": request.document_id,
            "filename": document["filename"],
            "created_at": datetime.now(UTC).isoformat(),
            "embedding_model": request.embedding_model,
            "top_k": request.top_k,
            "chunk_sizes": request.chunk_sizes,
            "overlap_percent": request.overlap_percent,
            "questions": request.questions,
            "measured_metrics": ["indexing_time_ms", "retrieval_latency_ms"],
        }

        question_vectors = self.embeddings.embed(request.questions)
        for chunk_size in request.chunk_sizes:
            overlap = int(chunk_size * request.overlap_percent / 100)
            chunks = self.documents.process_path(document_path, str(document["filename"]), chunk_size, overlap)
            vectors = self.embeddings.embed([chunk.content for chunk in chunks])
            for approach in request.vector_approaches:
                index_key = f"exp-{experiment_id.replace('-', '')[:28]}-{chunk_size}-{approach}"
                indexing_start = time.perf_counter()
                errors: list[str] = []
                try:
                    self.vector_store.add(
                        approach,
                        index_key,
                        chunks,
                        vectors,
                        document_id=request.document_id,
                        filename=str(document["filename"]),
                    )
                except ServiceError as error:
                    logger.exception(
                        "Experiment indexing failed for %s at chunk size %s.",
                        approach,
                        chunk_size,
                    )
                    errors.append(error.detail)
                indexing_time_ms = (
                    None if errors else (time.perf_counter() - indexing_start) * 1000
                )

                for question_index, question in enumerate(request.questions):
                    retrieved = []
                    run_errors = list(errors)
                    retrieval_latency_ms = None
                    if not errors:
                        retrieval_start = time.perf_counter()
                        try:
                            retrieved = self.vector_store.search(
                                approach,
                                index_key,
                                question_vectors[question_index],
                                request.top_k,
                            )
                            retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000
                        except ServiceError as error:
                            logger.exception(
                                "Experiment retrieval failed for %s at chunk size %s.",
                                approach,
                                chunk_size,
                            )
                            run_errors.append(error.detail)
                        if not run_errors and not retrieved:
                            run_errors.append("No chunks were retrieved for this question.")
                    manually_relevant_ids = set(
                        request.relevant_chunk_ids_by_question.get(question, [])
                    )
                    retrieved_chunks = []
                    for item in retrieved:
                        chunk_id = str(item["chunk_id"])
                        is_manually_relevant = chunk_id in manually_relevant_ids
                        retrieved_chunks.append({
                            "chunk_id": chunk_id,
                            "content": str(item["content"]),
                            "filename": str(item["filename"]),
                            "page_number": item.get("page_number"),
                            "relevance_score": float(item["relevance_score"]),
                            "similarity_score": float(item["relevance_score"]),
                            "manual_relevance": "relevant" if is_manually_relevant else None,
                            "context_contains_answer": None,
                            "evaluation_source": "manual_supplied" if is_manually_relevant else "not_evaluated",
                        })
                    result_runs.append({
                        "chunk_size": chunk_size,
                        "overlap": overlap,
                        "chunk_count": len(chunks),
                        "vector_approach": approach,
                        "question": question,
                        "indexing_time_ms": indexing_time_ms,
                        "retrieval_latency_ms": retrieval_latency_ms,
                        "retrieved_chunks": retrieved_chunks,
                        "errors": run_errors,
                        "status": (
                            "completed"
                            if not run_errors
                            and indexing_time_ms is not None
                            and retrieval_latency_ms is not None
                            and bool(retrieved_chunks)
                            else "failed"
                        ),
                    })

        result: dict[str, object] = {
            "experiment_id": experiment_id,
            **settings_snapshot,
            "runs": result_runs,
        }
        with self._lock:
            self._save_result(result)
        logger.info("Experiment %s produced %s result rows.", experiment_id, len(result_runs))
        return result

    def update_manual_evaluations(
        self,
        experiment_id: str,
        evaluations: list[ManualChunkEvaluation],
    ) -> dict[str, object]:
        path = self._result_path(experiment_id)
        if not path.is_file():
            raise ServiceError(404, "Experiment not found.")
        requested = {
            (evaluation.chunk_size, evaluation.question, evaluation.chunk_id): evaluation
            for evaluation in evaluations
        }
        updated = 0
        with self._lock:
            result = self._load_result(path)
            runs = result.get("runs")
            if not isinstance(runs, list):
                raise ServiceError(500, "Experiment results have an invalid runs format.")
            for run in runs:
                if not isinstance(run, dict) or not isinstance(run.get("retrieved_chunks"), list):
                    continue
                chunk_size = run.get("chunk_size")
                question = run.get("question")
                for chunk in run["retrieved_chunks"]:
                    if not isinstance(chunk, dict):
                        continue
                    evaluation = requested.get((
                        chunk_size,
                        question,
                        str(chunk.get("chunk_id")),
                    ))
                    if evaluation is None:
                        continue
                    chunk["manual_relevance"] = evaluation.relevance
                    if evaluation.context_contains_answer is not None:
                        chunk["context_contains_answer"] = evaluation.context_contains_answer
                    chunk["evaluation_source"] = "manual_review"
                    chunk["evaluation_note"] = evaluation.note
                    updated += 1
            if updated == 0:
                raise ServiceError(404, "None of the supplied chunk IDs were found in this experiment.")
            self._save_result(result)
        return {
            "experiment_id": experiment_id,
            "updated_evaluations": updated,
            "message": "Manual evaluations saved to the experiment JSON record.",
        }
