# Research Lens API

FastAPI backend for document indexing, retrieval-augmented question answering, and ChromaDB/FAISS retrieval experiments. It does not save chat history or use SQLite. Uploaded documents, indexes, document metadata, and experiment records remain in their existing `data/` directories.

## Architecture

```text
React/Vite frontend
  -> FastAPI routes
     -> document service (PDF/TXT extraction and chunking)
     -> Sentence Transformers (all-MiniLM-L6-v2)
     -> persistent ChromaDB / optional FAISS
     -> retrieval service (cosine similarity, top-k 5)
     -> Groq service (server-side, retrieved context only)
     -> experiment service (measured runs and JSON records)
```

The frontend uses `http://127.0.0.1:8001` in this workspace because port 8000 is already occupied by another local application. Configure `VITE_API_BASE_URL` in the frontend to match the backend port you run.

## Requirements and Windows setup

Python 3.11 or newer is recommended. Python 3.11 or 3.12 generally has the broadest package-wheel availability for Windows. FAISS CPU wheels may not be available for every Python/Windows combination; use a supported Python environment and confirm `python -c "import faiss"` before testing FAISS.

In PowerShell:

```powershell
cd C:\Users\Admin\Desktop\ragandvector\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\start_backend.ps1
```

The launcher uses the backend's `.venv`, starts Uvicorn on `127.0.0.1:8001`, and stays in the foreground. Keep the terminal open while using the frontend; press `Ctrl+C` to stop the API. If the Research Lens API is already healthy on that port, the script reports that instead of starting a second server. If another process is using the port, it reports the conflict instead of failing with a generic Windows bind error.

To use another port, run `.\start_backend.ps1 -Port 8010` and set `VITE_API_BASE_URL=http://127.0.0.1:8010` in `frontend/.env.local`, then restart Vite. The default frontend configuration uses port 8001.

If activation is blocked, install dependencies with `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`; the launcher can then be run normally.

Open `http://127.0.0.1:8001/docs` for the interactive API documentation. Health is at `http://127.0.0.1:8001/health`.

## Environment

Set values in `backend/.env`. Keep this file private and out of version control.

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | unset | Backend-only credential, required for LLM answers |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq model used for generation |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Shared document and query embedding model |
| `CHUNK_SIZE` | `800` | Default document chunk size |
| `CHUNK_OVERLAP` | `160` | Default document overlap |
| `MAX_UPLOAD_BYTES` | `26214400` | Maximum upload size |

No API key is returned or logged. Experiments and upload/index functions do not need a Groq key.

## API endpoints

- `GET /health` — reports API availability and service identity.
- `POST /api/upload` — accepts a PDF or TXT file as multipart form data, extracts text, creates chunks and embeddings, then indexes the document.
- `GET /api/documents` — lists indexed documents.
- `DELETE /api/documents/{document_id}` — removes an indexed document and its stored file.
- `POST /api/generate` — retrieves up to five chunks and generates an answer using the configured Groq model.
- `GET /api/experiments` — returns experiment settings and saved experiment records.
- `POST /api/experiments/run` — runs paired ChromaDB and FAISS measurements for all required chunk sizes.
- `POST /api/experiments/{experiment_id}/evaluations` — saves manually assigned relevance labels to the experiment JSON record. Each evaluation is scoped to its chunk size, question, and chunk ID so a label does not spill over to a different configuration or question.

Example manual evaluation:

```json
{
  "evaluations": [
    {
      "chunk_id": "retrieved-chunk-id",
      "chunk_size": 400,
      "question": "What is the main finding?",
      "relevance": "relevant",
      "context_contains_answer": true
    }
  ]
}
```

Example question request:

```json
{
  "question": "What method did the authors use?",
  "document_id": "document-id-from-upload",
  "vector_database": "chroma"
}
```

`vector_database` accepts `chroma` or `faiss`; top-k is fixed at five. Answers use retrieved context only, return real source metadata, and explain when the available context is insufficient. If Groq is unavailable or unconfigured, the API returns an error rather than a fabricated answer.

Example experiment request:

```json
{
  "document_id": "document-id-from-upload",
  "chunk_sizes": [200, 400, 600, 800, 1000],
  "overlap_percent": 20,
  "top_k": 5,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "vector_approaches": ["chroma", "faiss"],
  "questions": ["What is the main finding?"]
}
```

The same document and questions are used throughout the run. Each chunk-size configuration is embedded once, and the same vectors are sent to both stores. Indexing and retrieval timings are measured; cosine similarity is not a relevance judgment. Researchers add manual relevance labels separately. Failed or incomplete configurations include errors and are not represented as successful measurements. FAISS unavailability is reported per configuration.

## Tests

From `backend` with its virtual environment active:

```powershell
python -m pytest -q
```

The automated suite uses test doubles for embeddings, vector stores, and Groq, so basic API tests do not require a Groq key or model download. These tests do not substitute for separately exercising live model and vector-index behavior.

## Storage and history

There is no chat-history route or persistence. New questions and answers are not written to SQLite. The existing `data/history.db` file is intentionally left untouched. Document metadata and experiment records use structured JSON files, and vector stores/upload files remain under `data/`; SQLite integration is not included.
