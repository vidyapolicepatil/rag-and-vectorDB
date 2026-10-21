import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.errors import ServiceError
from app.routes import chat, documents, experiments, health
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService
from app.services.experiment_service import ExperimentService
from app.services.groq_service import GroqService
from app.services.retrieval_service import RetrievalService
from app.services.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


class AppServices:
    def __init__(self, settings: Settings) -> None:
        embeddings = EmbeddingService(settings)
        vector_store = VectorStore(settings)
        self.documents = DocumentService(settings, embeddings, vector_store)
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.retrieval = RetrievalService(settings, self.documents, embeddings, vector_store)
        self.groq = GroqService(settings)
        self.experiments = ExperimentService(settings, self.documents, embeddings, vector_store)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.services = AppServices(app_settings)
        yield

    application = FastAPI(
        title="Research Lens API",
        description=(
            "Backend API for PDF/TXT ingestion, retrieval-augmented question answering, "
            "and ChromaDB versus FAISS research experiments."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    application.include_router(health.router)
    application.include_router(documents.router)
    application.include_router(chat.router)
    application.include_router(experiments.router)

    @application.exception_handler(ServiceError)
    async def service_error_handler(_: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    @application.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, error: Exception) -> JSONResponse:
        logger.exception("Unhandled API error (%s).", type(error).__name__)
        return JSONResponse(status_code=500, content={"detail": "An unexpected backend error occurred."})

    return application


app = create_app()
