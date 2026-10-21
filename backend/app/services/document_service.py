import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import BinaryIO, Iterator, TextIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import Settings
from app.errors import ServiceError
from app.schemas import DocumentSummary
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)
CHUNK_SIZE_LIMIT = 10000
MAX_DOCUMENT_CHUNKS = 50000


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    content: str
    page_number: int | None


def split_text(text: str, size: int, overlap: int, page_number: int | None = None) -> list[TextChunk]:
    if size < 1 or size > CHUNK_SIZE_LIMIT:
        raise ServiceError(422, f"Chunk size must be between 1 and {CHUNK_SIZE_LIMIT} characters.")
    if overlap < 0 or overlap >= size:
        raise ServiceError(422, "Chunk overlap must be at least 0 and less than the chunk size.")
    chunks: list[TextChunk] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        content = text[start:end].strip()
        if content:
            chunks.append(TextChunk(str(uuid.uuid4()), content, page_number))
            if len(chunks) > MAX_DOCUMENT_CHUNKS:
                raise ServiceError(413, "The document would produce too many chunks to index.")
        if end == len(text):
            break
        start = end - overlap
    return chunks


def split_stream(stream: TextIO, size: int, overlap: int) -> list[TextChunk]:
    if size < 1 or size > CHUNK_SIZE_LIMIT:
        raise ServiceError(422, f"Chunk size must be between 1 and {CHUNK_SIZE_LIMIT} characters.")
    if overlap < 0 or overlap >= size:
        raise ServiceError(422, "Chunk overlap must be at least 0 and less than the chunk size.")
    chunks: list[TextChunk] = []
    step = size - overlap
    buffer = ""
    while block := stream.read(64 * 1024):
        buffer += block
        while len(buffer) > size:
            content = buffer[:size].strip()
            if content:
                chunks.append(TextChunk(str(uuid.uuid4()), content, None))
                if len(chunks) > MAX_DOCUMENT_CHUNKS:
                    raise ServiceError(413, "The document would produce too many chunks to index.")
            buffer = buffer[step:]
    if buffer.strip():
        chunks.append(TextChunk(str(uuid.uuid4()), buffer.strip(), None))
    return chunks


class DocumentService:
    def __init__(self, settings: Settings, embeddings: EmbeddingService, vector_store) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.uploads_directory = settings.uploads_directory
        self.manifest_path = self.uploads_directory / "documents.json"
        self._manifest_lock = RLock()
        self.uploads_directory.mkdir(parents=True, exist_ok=True)

    def _read_manifest(self) -> dict[str, dict[str, object]]:
        if not self.manifest_path.exists():
            return {}
        try:
            with self.manifest_path.open("r", encoding="utf-8") as manifest_file:
                content = json.load(manifest_file)
        except (OSError, json.JSONDecodeError) as error:
            logger.exception("Unable to read the document manifest.")
            raise ServiceError(500, "The document manifest could not be read.") from error
        if not isinstance(content, dict):
            raise ServiceError(500, "The document manifest has an invalid format.")
        return content

    def _write_manifest(self, documents: dict[str, dict[str, object]]) -> None:
        temporary_path = self.manifest_path.with_suffix(".tmp")
        try:
            with temporary_path.open("w", encoding="utf-8") as manifest_file:
                json.dump(documents, manifest_file, ensure_ascii=False, indent=2)
                manifest_file.flush()
                os.fsync(manifest_file.fileno())
            temporary_path.replace(self.manifest_path)
        except OSError as error:
            temporary_path.unlink(missing_ok=True)
            logger.exception("Unable to persist the document manifest.")
            raise ServiceError(500, "Document metadata could not be saved.") from error

    def _save_upload(self, source: BinaryIO, suffix: str) -> tuple[Path, int]:
        handle = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix="upload-",
            suffix=suffix,
            dir=self.uploads_directory,
            delete=False,
        )
        temporary_path = Path(handle.name)
        size = 0
        try:
            with handle:
                while block := source.read(1024 * 1024):
                    size += len(block)
                    if size > self.settings.max_upload_bytes:
                        raise ServiceError(
                            413,
                            f"File exceeds the {self.settings.max_upload_bytes // (1024 * 1024)} MB upload limit.",
                        )
                    handle.write(block)
            if size == 0:
                raise ServiceError(422, "The uploaded file is empty.")
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return temporary_path, size

    def _extract_pdf_text(self, path: Path) -> Iterator[tuple[int, str]]:
        try:
            with path.open("rb") as pdf_file:
                reader = PdfReader(pdf_file, strict=True)
                if reader.is_encrypted:
                    raise ServiceError(422, "Password-protected PDF files are not supported.")
                for page_number, page in enumerate(reader.pages, start=1):
                    yield page_number, page.extract_text() or ""
        except ServiceError:
            raise
        except (PdfReadError, OSError, ValueError) as error:
            raise ServiceError(422, "The PDF file could not be read. Verify that it is a valid PDF.") from error

    def process_path(self, path: Path, filename: str, chunk_size: int, overlap: int) -> list[TextChunk]:
        suffix = Path(filename).suffix.lower()
        if suffix == ".txt":
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as text_file:
                    chunks = split_stream(text_file, chunk_size, overlap)
            except (UnicodeDecodeError, OSError) as error:
                raise ServiceError(422, "The TXT file must contain readable UTF-8 text.") from error
        else:
            chunks = []
            for page_number, text in self._extract_pdf_text(path):
                if text.strip():
                    chunks.extend(split_text(text, chunk_size, overlap, page_number))
                    if len(chunks) > MAX_DOCUMENT_CHUNKS:
                        raise ServiceError(413, "The document would produce too many chunks to index.")
        if not chunks:
            raise ServiceError(422, "No extractable text was found in the document.")
        return chunks

    def upload(self, source: BinaryIO, filename: str | None) -> DocumentSummary:
        safe_filename = Path((filename or "").replace("\\", "/")).name
        suffix = Path(safe_filename).suffix.lower()
        if suffix not in {".pdf", ".txt"}:
            raise ServiceError(415, "Only PDF and TXT files are supported.")

        temporary_path, size_bytes = self._save_upload(source, suffix)
        document_id = str(uuid.uuid4())
        final_path = self.uploads_directory / f"{document_id}{suffix}"
        index_key = f"doc-{document_id.replace('-', '')}"
        indexed_databases: list[str] = []
        moved = False
        try:
            chunks = self.process_path(temporary_path, safe_filename, self.settings.chunk_size, self.settings.chunk_overlap)
            vectors = self.embeddings.embed([chunk.content for chunk in chunks])
            self.vector_store.add(
                "chroma",
                index_key,
                chunks,
                vectors,
                document_id=document_id,
                filename=safe_filename,
            )
            indexed_databases.append("chroma")
            if self.vector_store.faiss_available():
                self.vector_store.add(
                    "faiss",
                    index_key,
                    chunks,
                    vectors,
                    document_id=document_id,
                    filename=safe_filename,
                )
                indexed_databases.append("faiss")
            temporary_path.replace(final_path)
            moved = True

            with self._manifest_lock:
                documents = self._read_manifest()
                uploaded_at = datetime.now(UTC).isoformat()
                metadata = {
                    "document_id": document_id,
                    "filename": safe_filename,
                    "chunk_count": len(chunks),
                    "uploaded_at": uploaded_at,
                    "size_bytes": size_bytes,
                    "file_path": final_path.name,
                }
                documents[document_id] = metadata
                self._write_manifest(documents)
            logger.info("Indexed document %s with %s chunks.", document_id, len(chunks))
            return DocumentSummary(**{key: value for key, value in metadata.items() if key != "file_path"})
        except ServiceError:
            self._rollback_indexes(indexed_databases, index_key)
            if moved:
                final_path.unlink(missing_ok=True)
            temporary_path.unlink(missing_ok=True)
            raise
        except Exception as error:
            self._rollback_indexes(indexed_databases, index_key)
            if moved:
                final_path.unlink(missing_ok=True)
            temporary_path.unlink(missing_ok=True)
            logger.exception("Document processing failed for %s.", document_id)
            raise ServiceError(500, "Document processing failed. No document was registered.") from error

    def _rollback_indexes(self, vector_databases: list[str], index_key: str) -> None:
        for vector_database in reversed(vector_databases):
            try:
                self.vector_store.delete(vector_database, index_key)
            except ServiceError:
                logger.exception("Unable to roll back the %s index after document processing failed.", vector_database)

    def list_documents(self) -> list[DocumentSummary]:
        with self._manifest_lock:
            documents = self._read_manifest()
        return [
            DocumentSummary(**{key: value for key, value in item.items() if key != "file_path"})
            for item in documents.values()
        ]

    def get_document(self, document_id: str) -> dict[str, object]:
        with self._manifest_lock:
            document = self._read_manifest().get(document_id)
        if document is None:
            raise ServiceError(404, "Document not found.")
        return dict(document)

    def get_document_path(self, document_id: str) -> Path:
        document = self.get_document(document_id)
        filename = str(document["file_path"])
        path = (self.uploads_directory / filename).resolve()
        if path.parent != self.uploads_directory.resolve() or not path.is_file():
            raise ServiceError(404, "The uploaded document file is unavailable.")
        return path

    def delete_document(self, document_id: str) -> None:
        with self._manifest_lock:
            documents = self._read_manifest()
            document = documents.get(document_id)
            if document is None:
                raise ServiceError(404, "Document not found.")
            index_key = f"doc-{document_id.replace('-', '')}"
            self.vector_store.delete("chroma", index_key)
            self.vector_store.delete("faiss", index_key)
            filename = str(document.get("file_path", ""))
            path = (self.uploads_directory / filename).resolve()
            if path.parent == self.uploads_directory.resolve():
                path.unlink(missing_ok=True)
            del documents[document_id]
            self._write_manifest(documents)

    def document_ids(self) -> list[str]:
        with self._manifest_lock:
            return list(self._read_manifest())
