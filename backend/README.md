# Research Lens Backend

FastAPI service for indexing research documents, retrieving relevant passages, generating grounded answers, and measuring ChromaDB and FAISS retrieval. The React/Vite frontend connects to this API at `http://127.0.0.1:8001` by default.

## Features

- Accepts PDF and UTF-8 TXT uploads.
- Extracts text, splits it into chunks, and generates embeddings with `sentence-transformers/all-MiniLM-L6-v2`.
- Stores document vectors in persistent ChromaDB and, when FAISS is installed, also keeps a FAISS index.
- Retrieves up to five matching passages and their source metadata.
- Sends retrieved context—not the original complete document—to Groq for question answering.
- Runs paired ChromaDB/FAISS research experiments with real indexing and retrieval measurements.
- Stores document metadata and experiment records as JSON files.
- Does not save chat history and does not use SQLite.

## Architecture

```text
app/main.py
  ├── routes/         Health, document, question-answering, and experiment endpoints
  ├── schemas.py      Pydantic request and response models
  └── services/
      ├── document_service.py    Upload validation, extraction, chunking, manifest
      ├── embedding_service.py   Shared Sentence Transformers model
      ├── vector_store.py        ChromaDB and FAISS indexing and search
      ├── retrieval_service.py   Query embedding and top-k retrieval
      ├── groq_service.py        Server-side answer generation
      └── experiment_service.py  Paired measurements and JSON records
```

## Requirements

- Windows 10/11 and PowerShell (commands below are for Windows).
- Python 3.11 or 3.12 recommended.
- Dependencies from `requirements.txt`.
- A Groq API key for live answer generation.

FAISS CPU wheels are not available for every Windows/Python combination. The API can report FAISS experiment failures if FAISS cannot be installed or imported. Upload and ChromaDB functions do not require a Groq key.

## Installation and configuration

Open PowerShell in the backend directory:

```powershell
cd C:\Users\Admin\Desktop\ragandvector\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create the local environment file only if it does not already exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `backend\.env` and set your Groq key for question answering:

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
```

Keep `.env` private. It is ignored by Git. Never put a Groq key in the frontend or commit it to the repository. Do not overwrite an existing `.env` when updating the project.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | Empty | Backend-only key; required for live LLM answers |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq model name |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model for documents and questions |
| `CHUNK_SIZE` | `800` | Default document chunk size, in characters |
| `CHUNK_OVERLAP` | `160` | Default document overlap, in characters |
| `MAX_UPLOAD_BYTES` | `26214400` | Upload limit in bytes (25 MiB) |

Experiment settings are separately fixed by API validation: chunk sizes 200/400/600/800/1000, 20% overlap, top-k 5, both ChromaDB and FAISS, and the model above.

## Run the backend

From `backend`, run:

```powershell
.\start_backend.ps1
```

The script starts Uvicorn on `127.0.0.1:8001` and keeps it in the foreground. Leave this terminal open while using the frontend; press `Ctrl+C` to stop the API. If Research Lens is already healthy on port 8001, the launcher reports that instead of starting a duplicate process. If another application owns the port, it reports the conflict.

If PowerShell blocks script execution, start Uvicorn directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

To use a different port:

```powershell
.\start_backend.ps1 -Port 8010
```

Set `VITE_API_BASE_URL=http://127.0.0.1:8010` in `frontend\.env.local` and restart Vite as well. The frontend and backend ports must match.

### Verify the server

- Health check: <http://127.0.0.1:8001/health>
- Interactive API docs: <http://127.0.0.1:8001/docs>
- OpenAPI schema: <http://127.0.0.1:8001/openapi.json>

The health endpoint should return:

```json
{
  "status": "ok",
  "service": "research-lens-api"
}
```

CORS allows the development frontend origins `http://localhost:5173` and `http://127.0.0.1:5173`.

## API reference

All request bodies and responses are validated using Pydantic. Error responses use a JSON `detail` field.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Check that this API is running |
| `POST` | `/api/upload` | Upload and index a PDF or TXT document (multipart field: `file`) |
| `GET` | `/api/documents` | List indexed documents |
| `DELETE` | `/api/documents/{document_id}` | Delete a document, its file, and its vector indexes |
| `POST` | `/api/generate` | Retrieve relevant context and generate an answer |
| `GET` | `/api/experiments` | Get experiment configurations and saved results |
| `POST` | `/api/experiments/run` | Run the paired chunk-size/vector-store comparison |
| `POST` | `/api/experiments/{experiment_id}/evaluations` | Save manual relevance labels |

### Upload a document

Use Swagger UI at `/docs` to call `POST /api/upload`; select a PDF or TXT file in the `file` field. The service checks the extension and size, saves the upload, extracts text, builds chunks and embeddings, and completes indexing before returning success. Empty, invalid, unreadable, encrypted, or unsupported files return an error.

On success, the response includes the generated `document_id`, filename, chunk count, size, upload time, and `indexed: true`. Upload limit defaults to 25 MiB.

### Ask a question

`POST /api/generate` request:

```json
{
  "question": "What method did the authors use?",
  "document_id": "document-id-from-upload",
  "vector_database": "chroma"
}
```

`document_id` is optional; if omitted, retrieval searches all registered documents. `vector_database` accepts `chroma` or `faiss` and defaults to `chroma`. The backend embeds the question using the same model used for document chunks, retrieves at most five passages, and sends only those passages to Groq. A successful response includes the answer, source references, retrieved metadata, and timing breakdown. If Groq is not configured or the provider fails, the API returns an error instead of inventing an answer.

### Compare ChromaDB and FAISS

`POST /api/experiments/run` uses one indexed document and the same evaluation question list for both vector approaches:

```json
{
  "document_id": "document-id-from-upload",
  "chunk_sizes": [200, 400, 600, 800, 1000],
  "overlap_percent": 20,
  "top_k": 5,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "vector_approaches": ["chroma", "faiss"],
  "questions": [
    "What is the main finding?",
    "Which method did the authors use?"
  ]
}
```

Configuration constraints are validated: all five chunk sizes, 20% overlap, top-k 5, the shared embedding model, and both vector approaches are required. Each chunk size produces one chunk set and embedding matrix; the same vectors are indexed by both databases. Measurements include indexing time, retrieval latency, chunk IDs, returned content, and cosine similarity when available. Failed or incomplete runs include errors and are not marked completed.

`GET /api/experiments` returns the available configuration and saved result records. Manual labels can be saved to `POST /api/experiments/{experiment_id}/evaluations`:

```json
{
  "evaluations": [
    {
      "chunk_id": "retrieved-chunk-id",
      "chunk_size": 400,
      "question": "What is the main finding?",
      "relevance": "relevant",
      "context_contains_answer": true,
      "note": "Optional reviewer note"
    }
  ]
}
```

`relevance` must be `relevant`, `partially_relevant`, or `not_relevant`. Manual labels are evaluations—not measured metrics—and are scoped to the question, chunk size, and chunk ID. Cosine similarity must not be treated as a human relevance label. If FAISS is unavailable, its affected experiment runs report errors; ChromaDB measurements do not imply FAISS succeeded.

## Data and persistence

Data is stored locally under `backend\data\`:

| Path | Contents |
|---|---|
| `uploads\` | Uploaded PDF/TXT files and `documents.json` manifest |
| `chroma_db\` | Persistent ChromaDB collections |
| `faiss_index\` | FAISS `.index` files and corresponding JSON chunk metadata |
| `experiments\` | Saved experiment result JSON files |

Keep these directories when retaining documents, vector indexes, or experiment results. They may contain private research content. Generated data is excluded from Git.

Chat history is not stored. SQLite integration is intentionally not implemented. The existing `data\history.db`, if present, is unused and left untouched.

## Tests

Run the test suite from the backend folder:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover health, CORS, document validation and indexing, question validation and response behavior, experiment configuration, and vector retrieval. External Groq calls are mocked; tests do not require a live Groq key. Tests using actual FAISS indexes are skipped if FAISS is unavailable.

## Troubleshooting

### `WinError 10048` / address already in use

Port 8001 is occupied. Check <http://127.0.0.1:8001/health>. If it returns the Research Lens service identity, the backend is already running; do not start a second copy. `start_backend.ps1` performs this check. If another program owns the port, select an available port with `.\start_backend.ps1 -Port 8010` and update the frontend's `VITE_API_BASE_URL` to match.

### Frontend cannot connect

1. Start the API with `.\start_backend.ps1` and leave its terminal open.
2. Check that `/health` returns `research-lens-api`.
3. Check `frontend\.env.local` contains `VITE_API_BASE_URL=http://127.0.0.1:8001`.
4. Restart Vite after changing the frontend environment file.

### Groq answer generation fails

Check `GROQ_API_KEY` and `GROQ_MODEL` in `backend\.env`, and restart the API after editing. Never expose the key in frontend code or logs.

### FAISS is unavailable

Verify FAISS from the backend virtual environment:

```powershell
.\.venv\Scripts\python.exe -c "import faiss; print('FAISS is available')"
```

If import fails, use a Python version with a compatible `faiss-cpu` wheel or install in a supported environment. The API reports FAISS failures in experiment results; it does not substitute fabricated measurements.
