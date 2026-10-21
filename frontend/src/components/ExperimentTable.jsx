import { FlaskConical } from "lucide-react";

function formatMilliseconds(value) {
  return Number.isFinite(value) ? `${value.toFixed(2)} ms` : "Not measured";
}

function isCompleted(run) {
  return run?.status === "completed"
    && !run.errors?.length
    && Number.isFinite(run.chunk_count)
    && run.chunk_count > 0
    && Number.isFinite(run.indexing_time_ms)
    && Number.isFinite(run.retrieval_latency_ms)
    && run.retrieved_chunks?.length > 0;
}

function RetrievedChunks({ run, onManualEvaluation }) {
  const chunks = run.retrieved_chunks || [];
  const evaluated = chunks.filter((chunk) => chunk.manual_relevance).length;

  if (!chunks.length) {
    return <span className="comparison-empty">{run.errors?.length ? "Retrieval failed" : "No chunks retrieved"}</span>;
  }

  return (
    <div className="experiment-relevance">
      <span>{evaluated ? `${evaluated}/${chunks.length} manually evaluated` : "Not manually evaluated"}</span>
      {chunks.map((chunk) => (
        <label key={chunk.chunk_id}>
          <span title={chunk.chunk_id}>{chunk.chunk_id}</span>
          <select
            aria-label={`Manual relevance for ${run.vector_approach}, ${run.chunk_size} characters, ${chunk.chunk_id}`}
            value={chunk.manual_relevance || ""}
            onChange={(event) => onManualEvaluation(run.chunk_size, run.question, chunk.chunk_id, event.target.value)}
          >
            <option value="" disabled>Choose label</option>
            <option value="relevant">Relevant</option>
            <option value="partially_relevant">Partially relevant</option>
            <option value="not_relevant">Not relevant</option>
          </select>
          <details>
            <summary>Text · cosine {Number.isFinite(chunk.similarity_score) ? chunk.similarity_score.toFixed(4) : "not provided"}</summary>
            <small>{chunk.filename}{chunk.page_number ? ` · page ${chunk.page_number}` : ""}</small>
            <p>{chunk.content}</p>
          </details>
        </label>
      ))}
    </div>
  );
}

function ApproachResults({ run, onManualEvaluation }) {
  if (!run) {
    return <div className="comparison-approach missing-result">No result returned</div>;
  }

  const completed = isCompleted(run);
  return (
    <div className="comparison-approach">
      <span className={`experiment-status ${completed ? "status-complete" : "status-failed"}`}>
        {completed ? "Completed" : "Failed"}
      </span>
      <dl className="comparison-metrics">
        <div><dt>Chunks indexed</dt><dd>{Number.isFinite(run.chunk_count) ? run.chunk_count : "Not indexed"}</dd></div>
        <div><dt>Indexing</dt><dd>{formatMilliseconds(run.indexing_time_ms)}</dd></div>
        <div><dt>Retrieval</dt><dd>{formatMilliseconds(run.retrieval_latency_ms)}</dd></div>
      </dl>
      {run.errors?.length > 0 && <small className="experiment-status-error">{run.errors.join("; ")}</small>}
      <RetrievedChunks run={run} onManualEvaluation={onManualEvaluation} />
    </div>
  );
}

function pairRuns(runs) {
  const groups = new Map();
  for (const run of runs) {
    const key = JSON.stringify([run.chunk_size, run.question]);
    if (!groups.has(key)) {
      groups.set(key, { chunk_size: run.chunk_size, overlap: run.overlap, question: run.question, chroma: null, faiss: null });
    }
    const group = groups.get(key);
    group[run.vector_approach] = run;
  }
  return [...groups.values()].sort((left, right) => (
    left.chunk_size - right.chunk_size
    || left.question.localeCompare(right.question)
  ));
}

export default function ExperimentTable({ runs, onManualEvaluation }) {
  const hasRuns = runs.length > 0;
  const completed = runs.filter(isCompleted).length;
  const pairs = pairRuns(runs);

  return (
    <section className="card experiment-table-card">
      <div className="section-heading">
        <div><span className="section-kicker">MEASURED COMPARISON</span><h2>Experiment results</h2></div>
        <span className={hasRuns && completed === runs.length ? "measured-tag" : "pending-tag"}>
          <FlaskConical size={14} />
          {hasRuns ? `${completed}/${runs.length} runs completed` : "AWAITING RESULTS"}
        </span>
      </div>
      {hasRuns ? (
        <>
          <div className="table-scroll comparison-table-scroll">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th rowSpan="2">Chunk size / overlap</th>
                  <th rowSpan="2">Question</th>
                  <th className="comparison-db-heading chroma-heading" colSpan="1">ChromaDB</th>
                  <th className="comparison-db-heading faiss-heading" colSpan="1">FAISS</th>
                </tr>
                <tr>
                  <th>Measured result and retrieved chunks</th>
                  <th>Measured result and retrieved chunks</th>
                </tr>
              </thead>
              <tbody>
                {pairs.map((pair) => (
                  <tr key={`${pair.chunk_size}-${pair.question}`}>
                    <td className="comparison-config">
                      <strong>{pair.chunk_size} chars</strong>
                      <small>{pair.overlap ?? "Not recorded"} chars overlap</small>
                    </td>
                    <td className="comparison-question">{pair.question}</td>
                    <td><ApproachResults run={pair.chroma} onManualEvaluation={onManualEvaluation} /></td>
                    <td><ApproachResults run={pair.faiss} onManualEvaluation={onManualEvaluation} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="measurement-legend">
            <span><i className="legend-measured" />Chunk counts, indexing, retrieval latency and cosine similarity are backend measurements.</span>
            <span><i className="legend-manual" />Relevance labels are entered by the researcher.</span>
          </div>
        </>
      ) : (
        <div className="experiment-empty-state">
          <span className="experiment-empty-icon"><FlaskConical size={22} /></span>
          <h3>No experiment results yet</h3>
          <p>Run a comparison to display measured indexing and retrieval results. No sample performance data is shown.</p>
        </div>
      )}
    </section>
  );
}
