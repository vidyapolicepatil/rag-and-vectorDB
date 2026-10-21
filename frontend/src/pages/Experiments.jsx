import { useEffect, useState } from "react";
import { BarChart3, Check, Download, Info, LoaderCircle, Play, Settings2 } from "lucide-react";
import ExperimentTable from "../components/ExperimentTable.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import {
  checkHealth,
  getExperiments,
  runRetrievalExperiment,
  saveExperimentEvaluations,
  uploadDocument,
} from "../services/api.js";

const CHUNK_SIZES = [200, 400, 600, 800, 1000];
const EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2";
const VECTOR_APPROACHES = ["chroma", "faiss"];

function normalizeRun(run) {
  if (
    !run
    || !Number.isFinite(run.chunk_size)
    || !VECTOR_APPROACHES.includes(run.vector_approach)
    || typeof run.question !== "string"
  ) {
    throw new Error("The backend returned an invalid experiment run.");
  }
  return {
    ...run,
    errors: Array.isArray(run.errors) ? run.errors : [],
    retrieved_chunks: Array.isArray(run.retrieved_chunks)
      ? run.retrieved_chunks.map((chunk) => ({
        ...chunk,
        chunk_id: String(chunk.chunk_id ?? "ID not provided"),
        similarity_score: Number.isFinite(chunk.similarity_score)
          ? chunk.similarity_score
          : Number.isFinite(chunk.relevance_score) ? chunk.relevance_score : null,
        manual_relevance: chunk.manual_relevance || "",
      }))
      : [],
    status: run.status || (
      Number.isFinite(run.chunk_count)
      && run.chunk_count > 0
      && Number.isFinite(run.indexing_time_ms)
      && Number.isFinite(run.retrieval_latency_ms)
      && Array.isArray(run.retrieved_chunks)
      && run.retrieved_chunks.length > 0
      && !run.errors?.length
        ? "completed"
        : "failed"
    ),
  };
}

function saveDownload(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function csvCell(value) {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

export default function Experiments() {
  const [documentFile, setDocumentFile] = useState(null);
  const [evaluationUpload, setEvaluationUpload] = useState(null);
  const [questionsInput, setQuestionsInput] = useState("");
  const [backendStatus, setBackendStatus] = useState("checking");
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [progressStatus, setProgressStatus] = useState("");
  const [runs, setRuns] = useState([]);
  const [experimentRecord, setExperimentRecord] = useState(null);
  const [experimentId, setExperimentId] = useState("");
  const [runLabel, setRunLabel] = useState("");
  const [savingEvaluations, setSavingEvaluations] = useState(false);
  const [evaluationsSaved, setEvaluationsSaved] = useState(false);

  const questions = questionsInput.split(/\r?\n/).map((question) => question.trim()).filter(Boolean);
  const settingsError = !questions.length
    ? "Add at least one evaluation question, one per line."
    : questions.length > 50
      ? "Enter no more than 50 evaluation questions."
      : questions.some((question) => question.length > 4000)
        ? "Questions cannot exceed 4,000 characters."
        : "";

  useEffect(() => {
    let active = true;
    checkHealth().then(() => {
      if (active) setBackendStatus("connected");
    }).catch(() => {
      if (active) setBackendStatus("unavailable");
    });
    getExperiments().then((response) => {
      if (!active || !Array.isArray(response?.results) || !response.results.length) return;
      const latest = [...response.results].sort(
        (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
      )[0];
      const loadedRuns = latest.runs.map(normalizeRun);
      setExperimentRecord(latest);
      setExperimentId(latest.experiment_id);
      setRuns(loadedRuns);
      setRunLabel(`${latest.filename || "Evaluation document"} · ${new Date(latest.created_at).toLocaleString()}`);
    }).catch((loadError) => {
      if (active) setError(`Saved experiment results could not be loaded: ${loadError.message}`);
    });
    return () => { active = false; };
  }, []);

  async function refreshBackendStatus() {
    setBackendStatus("checking");
    try {
      await checkHealth();
      setBackendStatus("connected");
    } catch {
      setBackendStatus("unavailable");
    }
  }

  function clearResults() {
    setRuns([]);
    setExperimentRecord(null);
    setExperimentId("");
    setRunLabel("");
    setEvaluationsSaved(false);
  }

  async function startExperiment(event) {
    event.preventDefault();
    if (!documentFile || settingsError || backendStatus !== "connected" || running) return;

    setError("");
    setRunning(true);
    setEvaluationsSaved(false);
    const label = `${documentFile.name} · ${new Date().toLocaleString()}`;
    const existingUpload = evaluationUpload?.file === documentFile ? evaluationUpload.document : null;
    setProgressStatus(existingUpload
      ? "Using the uploaded evaluation document..."
      : "Uploading the evaluation document and extracting its text...");
    try {
      let uploaded = existingUpload;
      if (!uploaded) {
        uploaded = await uploadDocument(documentFile);
      }
      if (!uploaded?.document_id) {
        throw new Error("The upload response did not include a document ID.");
      }
      if (!existingUpload) setEvaluationUpload({ file: documentFile, document: uploaded });

      setProgressStatus(`Running ${CHUNK_SIZES.length * VECTOR_APPROACHES.length * questions.length} paired retrieval measurements...`);
      const response = await runRetrievalExperiment({
        document_id: uploaded.document_id,
        chunk_sizes: CHUNK_SIZES,
        overlap_percent: 20,
        top_k: 5,
        embedding_model: EMBEDDING_MODEL,
        vector_approaches: VECTOR_APPROACHES,
        questions,
      });
      if (!Array.isArray(response?.runs)) {
        throw new Error("The experiment endpoint did not return a runs array.");
      }

      const normalizedRuns = response.runs.map(normalizeRun);
      const expectedCount = CHUNK_SIZES.length * VECTOR_APPROACHES.length * questions.length;
      if (normalizedRuns.length !== expectedCount) {
        throw new Error(`The backend returned ${normalizedRuns.length} runs; expected ${expectedCount}.`);
      }
      const received = new Set(normalizedRuns.map((run) => `${run.chunk_size}|${run.vector_approach}|${run.question}`));
      for (const size of CHUNK_SIZES) {
        for (const approach of VECTOR_APPROACHES) {
          for (const question of questions) {
            if (!received.has(`${size}|${approach}|${question}`)) {
              throw new Error(`The backend response is missing ${approach}, ${size} characters, or a configured question.`);
            }
          }
        }
      }
      if (normalizedRuns.some((run) => (
        run.retrieved_chunks.length > 5
        || (run.status === "completed" && (
          run.errors.length > 0
          || !Number.isFinite(run.chunk_count)
          || run.chunk_count < 1
          || !Number.isFinite(run.indexing_time_ms)
          || !Number.isFinite(run.retrieval_latency_ms)
          || run.retrieved_chunks.length === 0
        ))
      ))) {
        throw new Error("A completed backend result is missing measured timings, indexed chunks, or retrieved passages.");
      }
      setRuns(normalizedRuns);
      setExperimentRecord(response);
      setExperimentId(response.experiment_id);
      setRunLabel(label);
      setProgressStatus("");
    } catch (requestError) {
      setError(requestError.message);
      setProgressStatus("");
    } finally {
      setRunning(false);
    }
  }

  function updateManualEvaluation(chunkSize, question, chunkId, manualRelevance) {
    setEvaluationsSaved(false);
    setRuns((current) => current.map((run) => ({
      ...run,
      retrieved_chunks: run.retrieved_chunks.map((chunk) => (
        run.chunk_size === chunkSize
        && run.question === question
        && chunk.chunk_id === chunkId
          ? { ...chunk, manual_relevance: manualRelevance }
          : chunk
      )),
    })));
  }

  async function persistManualEvaluations() {
    const evaluations = new Map();
    for (const run of runs) {
      for (const chunk of run.retrieved_chunks) {
        if (chunk.manual_relevance) {
          const evaluationKey = `${run.chunk_size}|${run.question}|${chunk.chunk_id}`;
          evaluations.set(evaluationKey, {
            chunk_id: chunk.chunk_id,
            chunk_size: run.chunk_size,
            question: run.question,
            relevance: chunk.manual_relevance,
          });
        }
      }
    }
    if (!experimentId || !evaluations.size) {
      setError("Select a manual relevance label before saving evaluations.");
      return;
    }
    setSavingEvaluations(true);
    setError("");
    try {
      await saveExperimentEvaluations(experimentId, [...evaluations.values()]);
      setEvaluationsSaved(true);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSavingEvaluations(false);
    }
  }

  function exportResults() {
    if (!experimentRecord) return;
    const safeId = experimentRecord.experiment_id || "experiment";

    const headers = [
      "experiment_id", "document_id", "embedding_model", "top_k", "vector_approach",
      "chunk_size", "overlap", "chunk_count", "question", "indexing_time_ms",
      "retrieval_latency_ms", "chunk_id", "filename", "page_number", "similarity_score",
      "manual_relevance", "status", "content", "errors",
    ];
    const rows = [headers, ...runs.flatMap((run) => {
      const chunks = run.retrieved_chunks.length ? run.retrieved_chunks : [null];
      return chunks.map((chunk) => [
        experimentRecord.experiment_id,
        experimentRecord.document_id,
        experimentRecord.embedding_model,
        experimentRecord.top_k,
        run.vector_approach,
        run.chunk_size,
        run.overlap,
        run.chunk_count,
        run.question,
        run.indexing_time_ms,
        run.retrieval_latency_ms,
        chunk?.chunk_id,
        chunk?.filename,
        chunk?.page_number,
        chunk?.similarity_score,
        chunk?.manual_relevance,
        run.status,
        chunk?.content,
        run.errors.join(" | "),
      ]);
    })];
    const csv = rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
    saveDownload(`${safeId}.csv`, csv, "text/csv;charset=utf-8");
  }

  const canRun = Boolean(documentFile && !settingsError && backendStatus === "connected" && !running);

  return (
    <div className="page-stack">
      <section className="page-intro-card">
        <div className="intro-icon intro-violet"><BarChart3 size={21} /></div>
        <div>
          <span className="section-kicker">CONTROLLED RETRIEVAL EVALUATION</span>
          <h2>Compare ChromaDB and FAISS</h2>
          <p>Each chunk configuration is embedded once and indexed with the same vectors for both approaches. Similarity scores are retrieval measurements, not relevance judgments.</p>
        </div>
      </section>

      <div className={`backend-status-banner ${backendStatus === "connected" ? "backend-connected" : ""}`} role="status">
        <span className="backend-status-dot" />
        <p>
          <strong>
            {backendStatus === "connected" ? "Backend connected." : backendStatus === "checking" ? "Checking backend connection..." : "Backend unavailable."}
          </strong>{" "}
          {backendStatus === "connected" ? "Evaluation uploads and experiments are available." : "A successful GET /health check is required to run comparisons."}
        </p>
        {backendStatus !== "checking" && (
          <button type="button" className="button button-quiet backend-retry-button" onClick={refreshBackendStatus}>Check connection</button>
        )}
      </div>

      <form className="card experiment-setup-card" onSubmit={startExperiment}>
        <div className="section-heading">
          <div><span className="section-kicker">EXPERIMENT SETUP</span><h2>Configure a paired comparison</h2></div>
          <span className="soft-tag"><Settings2 size={13} /> SETTINGS</span>
        </div>

        <div className="experiment-form-grid">
          <div className="experiment-field experiment-field-wide">
            <label htmlFor="experiment-document">Evaluation document</label>
            <input
              id="experiment-document"
              type="file"
              accept=".pdf,.txt,application/pdf,text/plain"
              onChange={(event) => {
                setDocumentFile(event.target.files?.[0] || null);
                setEvaluationUpload(null);
                clearResults();
              }}
            />
            <small>{documentFile
              ? `${documentFile.name} · retained in the backend document store for repeatable runs`
              : "Upload one PDF or UTF-8 TXT file. The backend keeps it until you delete the document."}</small>
          </div>

          <fieldset className="experiment-field experiment-field-wide chunk-size-options">
            <legend>Chunk sizes (characters)</legend>
            <div className="experiment-fixed-configurations">
              {CHUNK_SIZES.map((size) => <span key={size}>{size} / {size * 0.2} chars overlap</span>)}
            </div>
            <small>All five sizes are included in every run, comparing ChromaDB and FAISS (ten configurations total).</small>
          </fieldset>

          <div className="experiment-field">
            <label htmlFor="top-k">Top-k retrieval</label>
            <input id="top-k" value="5" readOnly />
            <small>Fixed at five for every comparison.</small>
          </div>
          <div className="experiment-field">
            <label htmlFor="embedding-model">Embedding model</label>
            <input id="embedding-model" value={EMBEDDING_MODEL} readOnly />
            <small>Shared for chunk and question embeddings.</small>
          </div>
          <div className="experiment-field experiment-field-wide">
            <label>Vector approaches</label>
            <div className="approach-pair">
              <span><Check size={15} /> ChromaDB</span>
              <span><Check size={15} /> FAISS</span>
              <small>Both are executed on the backend using identical vectors and cosine similarity.</small>
            </div>
          </div>
          <div className="experiment-field experiment-field-wide">
            <label htmlFor="evaluation-questions">Evaluation questions</label>
            <textarea
              id="evaluation-questions"
              rows="4"
              value={questionsInput}
              onChange={(event) => { setQuestionsInput(event.target.value); clearResults(); }}
              placeholder={"One question per line\nWhat is the main finding?\nWhich method did the authors use?"}
            />
            <small>Each non-empty line is queried against both approaches and all five chunk sizes.</small>
          </div>
        </div>

        <div className="configuration-preview">
          <strong>Planned configurations</strong>
          <div className="planned-runs">
            {CHUNK_SIZES.map((size) => <span key={size}>{size} chars · {size * 0.2} overlap · ChromaDB + FAISS</span>)}
          </div>
          <small>10 configurations × {questions.length} questions · top-k 5 · {EMBEDDING_MODEL}</small>
        </div>

        {settingsError && <ErrorMessage message={settingsError} />}
        {error && <ErrorMessage message={error} onDismiss={() => setError("")} />}
        <div className="experiment-submit-row">
          <p><Info size={14} /> Timings and retrieved passages come from actual backend indexes; relevance is manually evaluated below.</p>
          <button type="submit" className="button button-primary experiment-run-button" disabled={!canRun}>
            {running
              ? <><LoaderCircle size={16} className="spin-icon" /> Running comparison...</>
              : <><Play size={15} /> Run comparison</>}
          </button>
        </div>
        {progressStatus && <div className="experiment-progress" role="status"><LoaderCircle size={15} className="spin-icon" />{progressStatus}</div>}
      </form>

      {runLabel && runs.length > 0 && (
        <div className="run-provenance"><Check size={15} /><span>Backend result set for <strong>{runLabel}</strong>.</span></div>
      )}
      {runs.length > 0 && (
        <div className="experiment-export-row">
          <button type="button" className="button button-secondary" onClick={() => exportResults()}><Download size={15} /> Export CSV</button>
        </div>
      )}
      <ExperimentTable
        runs={runs}
        onManualEvaluation={updateManualEvaluation}
      />
      {runs.length > 0 && (
        <div className="manual-save-note">
          <Info size={15} />
          <span>Cosine similarity is not a relevance score. Apply researcher relevance labels to retrieved chunks, then save them with the experiment record.</span>
          <button type="button" className="button button-secondary" onClick={persistManualEvaluations} disabled={savingEvaluations}>
            {savingEvaluations ? "Saving..." : evaluationsSaved ? "Evaluations saved" : "Save manual evaluations"}
          </button>
        </div>
      )}

      <section className="evaluation-tip">
        <span className="tip-number">01</span>
        <div><span className="section-kicker">METHODOLOGY</span><h3>Keep the comparison controlled</h3><p>The backend extracts one uploaded document, splits it independently at each selected size using a 20% overlap, creates one embedding matrix per size, and gives that same matrix to ChromaDB and FAISS. Indexing and retrieval latency are measured; relevance labels are researcher-entered and are never inferred from cosine similarity.</p></div>
      </section>
    </div>
  );
}
