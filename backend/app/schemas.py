from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


VectorDatabase = Literal["chroma", "faiss"]
VectorApproach = Literal["chroma", "faiss"]
ManualRelevance = Literal["relevant", "partially_relevant", "not_relevant"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["research-lens-api"] = "research-lens-api"


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    chunk_count: int
    uploaded_at: str
    size_bytes: int


class UploadResponse(DocumentSummary):
    indexed: Literal[True] = True
    message: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]


class DeleteResponse(BaseModel):
    document_id: str
    deleted: Literal[True] = True


class GenerateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=4000)
    document_id: str | None = None
    vector_database: VectorDatabase = "chroma"


class SourceReference(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    page_number: int | None = None


class RetrievalMetadata(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    page_number: int | None = None
    relevance_score: float
    content: str


class TimingInformation(BaseModel):
    embedding_ms: float
    retrieval_ms: float
    generation_ms: float
    total_ms: float


class GenerateResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    retrieval_metadata: list[RetrievalMetadata]
    timings: TimingInformation
    vector_database: VectorDatabase


class ExperimentRunRequest(BaseModel):
    document_id: str
    chunk_sizes: list[int] = Field(
        default_factory=lambda: [200, 400, 600, 800, 1000],
        min_length=5,
        max_length=5,
    )
    overlap_percent: Literal[20] = 20
    top_k: Literal[5] = 5
    embedding_model: Literal["sentence-transformers/all-MiniLM-L6-v2"] = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    vector_approaches: list[VectorApproach] = Field(
        default_factory=lambda: ["chroma", "faiss"], min_length=2, max_length=2
    )
    questions: list[str] = Field(min_length=1, max_length=50)
    relevant_chunk_ids_by_question: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("chunk_sizes")
    @classmethod
    def validate_chunk_sizes(cls, values: list[int]) -> list[int]:
        required_sizes = {200, 400, 600, 800, 1000}
        if set(values) != required_sizes or len(values) != len(required_sizes):
            raise ValueError("Every experiment must include chunk sizes 200, 400, 600, 800, and 1000.")
        return values

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, values: list[str]) -> list[str]:
        normalized = [question.strip() for question in values]
        if any(not question for question in normalized):
            raise ValueError("Questions cannot be empty.")
        if any(len(question) > 4000 for question in normalized):
            raise ValueError("Questions cannot exceed 4,000 characters.")
        return normalized

    @field_validator("vector_approaches")
    @classmethod
    def require_both_approaches(cls, values: list[VectorApproach]) -> list[VectorApproach]:
        if set(values) != {"chroma", "faiss"} or len(values) != 2:
            raise ValueError("Each comparison must include ChromaDB and FAISS exactly once.")
        return values


class ExperimentChunkResult(BaseModel):
    chunk_id: str
    content: str
    filename: str = ""
    page_number: int | None = None
    relevance_score: float | None = None
    similarity_score: float | None = None
    manual_relevance: ManualRelevance | None = None
    context_contains_answer: bool | None = None
    evaluation_source: Literal["manual_supplied", "manual_review", "not_evaluated"] = (
        "not_evaluated"
    )


class ExperimentRunResult(BaseModel):
    chunk_size: int
    overlap: int
    chunk_count: int | None = None
    vector_approach: VectorApproach
    question: str
    indexing_time_ms: float | None
    retrieval_latency_ms: float | None
    retrieved_chunks: list[ExperimentChunkResult]
    errors: list[str] = Field(default_factory=list)
    status: Literal["completed", "failed"] = "failed"

    @model_validator(mode="before")
    @classmethod
    def infer_legacy_status(cls, values: object) -> object:
        if not isinstance(values, dict) or values.get("status") is not None:
            return values

        errors = values.get("errors", [])
        chunks = values.get("retrieved_chunks", [])
        chunk_count = values.get("chunk_count")
        timings = (values.get("indexing_time_ms"), values.get("retrieval_latency_ms"))
        has_measurements = all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isfinite(value)
            and value >= 0
            for value in timings
        )
        completed = (
            not errors
            and isinstance(chunk_count, int)
            and not isinstance(chunk_count, bool)
            and chunk_count > 0
            and has_measurements
            and isinstance(chunks, list)
            and bool(chunks)
        )
        return {**values, "status": "completed" if completed else "failed"}


class ExperimentResultRecord(BaseModel):
    experiment_id: str
    document_id: str
    created_at: str
    embedding_model: str
    top_k: Literal[5]
    chunk_sizes: list[int]
    overlap_percent: int
    questions: list[str]
    measured_metrics: list[Literal["indexing_time_ms", "retrieval_latency_ms"]]
    runs: list[ExperimentRunResult]


class ExperimentsResponse(BaseModel):
    configurations: list[dict[str, object]]
    results: list[ExperimentResultRecord]


class ExperimentRunResponse(ExperimentResultRecord):
    pass


class ManualChunkEvaluation(BaseModel):
    chunk_id: str
    chunk_size: Literal[200, 400, 600, 800, 1000]
    question: str = Field(min_length=1, max_length=4000)
    relevance: ManualRelevance
    context_contains_answer: bool | None = None
    note: str | None = Field(default=None, max_length=1000)


class ManualEvaluationRequest(BaseModel):
    evaluations: list[ManualChunkEvaluation] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_chunk_evaluations(self) -> "ManualEvaluationRequest":
        evaluation_keys = [
            (evaluation.chunk_size, evaluation.question, evaluation.chunk_id)
            for evaluation in self.evaluations
        ]
        if len(set(evaluation_keys)) != len(evaluation_keys):
            raise ValueError("Each chunk can be evaluated only once per question and chunk size.")
        return self


class ManualEvaluationResponse(BaseModel):
    experiment_id: str
    updated_evaluations: int
    message: str
