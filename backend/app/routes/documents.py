import logging

from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies import get_services
from app.schemas import DeleteResponse, DocumentListResponse, UploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/upload", response_model=UploadResponse, status_code=201)
def upload_document(file: UploadFile = File(...), services=Depends(get_services)) -> UploadResponse:
    try:
        document = services.documents.upload(file.file, file.filename)
        return UploadResponse(
            **document.model_dump(),
            indexed=True,
            message="Document text was extracted, embedded, and indexed in ChromaDB.",
        )
    finally:
        file.file.close()


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(services=Depends(get_services)) -> DocumentListResponse:
    return DocumentListResponse(documents=services.documents.list_documents())


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
def delete_document(document_id: str, services=Depends(get_services)) -> DeleteResponse:
    services.documents.delete_document(document_id)
    logger.info("Deleted document %s.", document_id)
    return DeleteResponse(document_id=document_id)
