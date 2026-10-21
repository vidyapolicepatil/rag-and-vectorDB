import logging
import time

from fastapi import APIRouter, Depends

from app.dependencies import get_services
from app.errors import ServiceError
from app.schemas import GenerateRequest, GenerateResponse, RetrievalMetadata, SourceReference, TimingInformation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/generate", response_model=GenerateResponse)
def generate_answer(request: GenerateRequest, services=Depends(get_services)) -> GenerateResponse:
    if not request.question.strip():
        raise ServiceError(422, "Question must not be empty.")

    total_start = time.perf_counter()
    chunks, embedding_ms, retrieval_ms = services.retrieval.retrieve(
        request.question,
        request.vector_database,
        request.document_id,
    )
    generation_start = time.perf_counter()
    answer = services.groq.generate_answer(request.question, chunks)
    generation_ms = (time.perf_counter() - generation_start) * 1000

    sources = [
        SourceReference(
            document_id=str(chunk["document_id"]),
            filename=str(chunk["filename"]),
            chunk_id=str(chunk["chunk_id"]),
            page_number=chunk.get("page_number"),
        )
        for chunk in chunks
    ]
    metadata = [
        RetrievalMetadata(
            document_id=str(chunk["document_id"]),
            filename=str(chunk["filename"]),
            chunk_id=str(chunk["chunk_id"]),
            page_number=chunk.get("page_number"),
            relevance_score=float(chunk["relevance_score"]),
            content=str(chunk["content"]),
        )
        for chunk in chunks
    ]
    logger.info(
        "Generated an answer using %s with %s retrieved chunks.",
        request.vector_database,
        len(chunks),
    )
    return GenerateResponse(
        answer=answer,
        sources=sources,
        retrieval_metadata=metadata,
        timings=TimingInformation(
            embedding_ms=embedding_ms,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            total_ms=(time.perf_counter() - total_start) * 1000,
        ),
        vector_database=request.vector_database,
    )
    
