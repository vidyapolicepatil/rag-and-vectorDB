# Research Lens

Responsive React and Vite frontend for a document question-answering research project. The interface contains four sections: **Dashboard**, **Ask Documents**, **Experiments**, and **Research Notes**. Uploading, listing, and deleting documents are all available from Ask Documents.

## Run the frontend on Windows

Open PowerShell:

```powershell
cd C:\Users\Admin\Desktop\ragandvector\frontend
npm install
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`. For a production build, run `npm run build`.

## Backend connection

The frontend reads `VITE_API_BASE_URL` from the Vite environment. To override it, copy `.env.example` to `.env.local` only if you do not already have a local configuration file. This workspace uses `http://127.0.0.1:8001` because another local application is already using port 8000. Restart Vite after changing the URL.

The API service uses the backend's actual routes:

- `GET /health`
- `POST /api/upload`
- `GET /api/documents` and `DELETE /api/documents/{document_id}`
- `POST /api/generate`
- `GET /api/experiments`
- `POST /api/experiments/run`
- `POST /api/experiments/{experiment_id}/evaluations`

Health checks verify the Research Lens API service identifier; a different application on the configured port is not reported as a healthy backend. All API errors are shown to the user. Groq credentials belong only in the backend environment, never in this frontend.

## Pages and behavior

- **Dashboard** introduces the application and provides links to its main sections.
- **Ask Documents** uploads PDF and TXT files, lists and deletes indexed documents, and provides a single-column conversation page. Answers keep returned source metadata inline; there is no separate session or source-reference panel.
- **Experiments** runs paired ChromaDB and FAISS measurements on the same uploaded document and questions. Results are paired in one table row for each chunk-size/question combination, with measured metrics and retrieved chunks shown side by side. It always requests chunk sizes 200, 400, 600, 800, and 1000 characters, overlap 20%, top-k 5, and `sentence-transformers/all-MiniLM-L6-v2`. Every configuration's outcome is shown; failed or incomplete runs are not presented as completed. Indexing time, retrieval latency, and cosine similarity are backend measurements; relevance labels are manual researcher evaluations. CSV export contains only the backend response and current manual labels.
- **Research Notes** explains the RAG concepts in beginner-friendly language.

## Experiment methodology

Use the same source document and question list for each paired run. For each chunk size, the backend creates one chunk set and embedding matrix, then indexes those same vectors in ChromaDB and FAISS. The backend uses normalized vectors and cosine similarity, with top-k fixed at five. Indexing time measures vector-store indexing and persistence (not shared embedding generation); retrieval latency is measured for each question and vector approach.

No sample performance measurements or relevance judgments are included. Cosine similarity is not an automatic measure of human relevance. Researchers label retrieved passages as relevant, partially relevant, or not relevant. Experiment records and manual labels are stored by the backend in structured JSON files; this frontend does not store chat history or claim SQLite persistence.
