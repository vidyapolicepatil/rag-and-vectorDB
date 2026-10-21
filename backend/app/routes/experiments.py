from fastapi import APIRouter, Depends

from app.dependencies import get_services
from app.schemas import (
    ExperimentResultRecord,
    ExperimentRunRequest,
    ExperimentRunResponse,
    ExperimentsResponse,
    ManualEvaluationRequest,
    ManualEvaluationResponse,
)

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("", response_model=ExperimentsResponse)
def list_experiments(services=Depends(get_services)) -> ExperimentsResponse:
    return ExperimentsResponse(
        configurations=[
            {
                "chunk_sizes": [200, 400, 600, 800, 1000],
                "overlap_percent": 20,
                "top_k": 5,
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "vector_approaches": ["chroma", "faiss"],
            }
        ],
        results=[ExperimentResultRecord.model_validate(result) for result in services.experiments.list_results()],
    )


@router.post("/run", response_model=ExperimentRunResponse, status_code=201)
def run_experiment(
    request: ExperimentRunRequest,
    services=Depends(get_services),
) -> ExperimentRunResponse:
    result = services.experiments.run(request)
    return ExperimentRunResponse.model_validate(result)


@router.post("/{experiment_id}/evaluations", response_model=ManualEvaluationResponse)
def evaluate_experiment_chunks(
    experiment_id: str,
    request: ManualEvaluationRequest,
    services=Depends(get_services),
) -> ManualEvaluationResponse:
    result = services.experiments.update_manual_evaluations(experiment_id, request.evaluations)
    return ManualEvaluationResponse.model_validate(result)
