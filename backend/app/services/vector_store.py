import json
import logging
import re
import threading
from pathlib import Path

import numpy as np

from app.config import Settings
from app.errors import ServiceError
from app.services.document_service import TextChunk

logger = logging.getLogger(__name__)
INDEX_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,60}$")


class VectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.chroma_directory.mkdir(parents=True, exist_ok=True)
        self.settings.faiss_directory.mkdir(parents=True, exist_ok=True)
        self._chroma_client = None
        self._lock = threading.RLock()

    @staticmethod
    def _validate_database(vector_database: str) -> None:
        if vector_database not in {"chroma", "faiss"}:
            raise ServiceError(422, "vector_database must be 'chroma' or 'faiss'.")

    @staticmethod
    def _validate_index_key(index_key: str) -> None:
        if not INDEX_KEY_PATTERN.fullmatch(index_key):
            raise ServiceError(422, "The vector index identifier has an invalid format.")

    def _get_chroma_client(self):
        if self._chroma_client is None:
            try:
                import chromadb

                self._chroma_client = chromadb.PersistentClient(path=str(self.settings.chroma_directory))
            except Exception as error:
                logger.exception("ChromaDB initialization failed.")
                raise ServiceError(503, "ChromaDB could not be initialized.") from error
        return self._chroma_client

    def _get_collection(self, index_key: str):
        self._validate_index_key(index_key)
        try:
            return self._get_chroma_client().get_or_create_collection(
                name=index_key,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as error:
            logger.exception("ChromaDB collection access failed.")
            raise ServiceError(503, "The ChromaDB collection is unavailable.") from error

    def _faiss_paths(self, index_key: str) -> tuple[Path, Path]:
        self._validate_index_key(index_key)
        return (
            self.settings.faiss_directory / f"{index_key}.index",
            self.settings.faiss_directory / f"{index_key}.json",
        )

    @staticmethod
    def _load_faiss_module():
        try:
            import faiss
        except (ImportError, OSError) as error:
            raise ServiceError(
                503,
                "FAISS is not installed in the backend environment. Install the faiss-cpu dependency and restart the backend.",
            ) from error
        return faiss

    @staticmethod
    def faiss_available() -> bool:
        try:
            import faiss  # noqa: F401
        except (ImportError, OSError):
            return False
        return True

    def add(
        self,
        vector_database: str,
        index_key: str,
        chunks: list[TextChunk],
        vectors: np.ndarray,
        document_id: str,
        filename: str,
    ) -> None:
        self._validate_database(vector_database)
        self._validate_index_key(index_key)
        if len(chunks) != len(vectors) or not chunks:
            raise ServiceError(422, "Each indexed chunk must have exactly one embedding.")
        normalized_vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if normalized_vectors.ndim != 2 or normalized_vectors.shape[1] < 1:
            raise ServiceError(422, "Embeddings must be a two-dimensional vector matrix.")
        if not np.isfinite(normalized_vectors).all():
            raise ServiceError(422, "Embeddings contain invalid numeric values.")
        records = [
            {
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "document_id": document_id,
                "filename": filename,
                "page_number": chunk.page_number,
            }
            for chunk in chunks
        ]

        with self._lock:
            if vector_database == "chroma":
                self._add_chroma(index_key, records, normalized_vectors)
            else:
                self._add_faiss(index_key, records, normalized_vectors)

    def _add_chroma(self, index_key: str, records: list[dict[str, object]], vectors: np.ndarray) -> None:
        collection = self._get_collection(index_key)
        metadata = [
            {
                "document_id": str(record["document_id"]),
                "filename": str(record["filename"]),
                **(
                    {"page_number": int(record["page_number"])}
                    if record["page_number"] is not None
                    else {}
                ),
            }
            for record in records
        ]
        try:
            collection.add(
                ids=[str(record["chunk_id"]) for record in records],
                embeddings=vectors.tolist(),
                documents=[str(record["content"]) for record in records],
                metadatas=metadata,
            )
        except Exception as error:
            try:
                collection.delete(ids=[str(record["chunk_id"]) for record in records])
            except Exception:
                logger.exception("ChromaDB rollback failed after an indexing error.")
            logger.exception("ChromaDB indexing failed.")
            raise ServiceError(503, "ChromaDB indexing failed; the document was not registered.") from error

    def _add_faiss(self, index_key: str, records: list[dict[str, object]], vectors: np.ndarray) -> None:
        faiss = self._load_faiss_module()
        index_path, metadata_path = self._faiss_paths(index_key)
        if index_path.exists() or metadata_path.exists():
            raise ServiceError(409, "A FAISS index already exists for this document or experiment.")
        temporary_index = index_path.with_suffix(".index.tmp")
        temporary_metadata = metadata_path.with_suffix(".json.tmp")
        try:
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            metadata = [
                {**record, "position": position}
                for position, record in enumerate(records)
            ]
            faiss.write_index(index, str(temporary_index))
            with temporary_metadata.open("w", encoding="utf-8") as metadata_file:
                json.dump(metadata, metadata_file, ensure_ascii=False)
                metadata_file.flush()
            temporary_index.replace(index_path)
            temporary_metadata.replace(metadata_path)
        except (OSError, RuntimeError, ValueError) as error:
            temporary_index.unlink(missing_ok=True)
            temporary_metadata.unlink(missing_ok=True)
            index_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            logger.exception("FAISS index persistence failed.")
            raise ServiceError(503, "FAISS could not save its index and chunk metadata.") from error

    def search(
        self,
        vector_database: str,
        index_key: str,
        query_vector: np.ndarray,
        top_k: int,
    ) -> list[dict[str, object]]:
        self._validate_database(vector_database)
        self._validate_index_key(index_key)
        if top_k < 1:
            raise ServiceError(422, "top_k must be at least 1.")
        query = np.ascontiguousarray(query_vector, dtype=np.float32).reshape(1, -1)
        with self._lock:
            if vector_database == "chroma":
                return self._search_chroma(index_key, query, top_k)
            return self._search_faiss(index_key, query, top_k)

    def _search_chroma(
        self,
        index_key: str,
        query_vector: np.ndarray,
        top_k: int,
    ) -> list[dict[str, object]]:
        collection = self._get_collection(index_key)
        try:
            count = collection.count()
            if count == 0:
                return []
            result = collection.query(
                query_embeddings=query_vector.tolist(),
                n_results=min(top_k, count),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as error:
            logger.exception("ChromaDB retrieval failed: %s", error)
            raise ServiceError(503, f"ChromaDB retrieval failed: {error}") from error
        ids = result["ids"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]
        return [
            {
                "chunk_id": chunk_id,
                "content": content or "",
                **metadata,
                "relevance_score": 1.0 - float(distance),
            }
            for chunk_id, content, metadata, distance in zip(ids, documents, metadatas, distances)
        ]

    def _search_faiss(
        self,
        index_key: str,
        query_vector: np.ndarray,
        top_k: int,
    ) -> list[dict[str, object]]:
        faiss = self._load_faiss_module()
        index_path, metadata_path = self._faiss_paths(index_key)
        if not index_path.is_file() or not metadata_path.is_file():
            raise ServiceError(
                404,
                "No FAISS index exists for this document. Re-upload the document in an environment with FAISS installed.",
            )
        try:
            # Reload from disk for each query so persisted indexes are the source of truth.
            index = faiss.read_index(str(index_path))
            with metadata_path.open("r", encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)
            if index.ntotal == 0:
                return []
            scores, positions = index.search(query_vector, min(top_k, index.ntotal))
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            logger.exception("FAISS index retrieval failed.")
            raise ServiceError(503, "FAISS index or metadata could not be read.") from error
        results = []
        for score, position in zip(scores[0], positions[0]):
            if position < 0 or position >= len(metadata):
                continue
            record = metadata[position]
            results.append({
                **record,
                "relevance_score": float(score),
            })
        return results

    def delete(self, vector_database: str, index_key: str) -> None:
        self._validate_database(vector_database)
        self._validate_index_key(index_key)
        with self._lock:
            if vector_database == "chroma":
                try:
                    self._get_chroma_client().delete_collection(index_key)
                except Exception as error:
                    try:
                        self._get_chroma_client().get_collection(index_key)
                    except Exception:
                        return
                    logger.exception("ChromaDB collection deletion failed.")
                    raise ServiceError(503, "ChromaDB could not delete the document index.") from error
            else:
                index_path, metadata_path = self._faiss_paths(index_key)
                try:
                    index_path.unlink(missing_ok=True)
                    metadata_path.unlink(missing_ok=True)
                except OSError as error:
                    logger.exception("FAISS index deletion failed.")
                    raise ServiceError(503, "FAISS could not delete the document index.") from error
