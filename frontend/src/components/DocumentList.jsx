import { FileText, LoaderCircle, Trash2 } from "lucide-react";
import ErrorMessage from "./ErrorMessage.jsx";

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleString();
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentList({ documents, loading, error, onDelete, deletingId }) {
  return (
    <section className="card document-list-card">
      <div className="section-heading"><div><span className="section-kicker">INDEXED DOCUMENTS</span><h2>Document library</h2></div></div>
      {error && <ErrorMessage message={error} />}
      {loading ? (
        <div className="documents-loading"><LoaderCircle size={17} className="spin-icon" /> Loading documents...</div>
      ) : documents.length ? (
        <div className="document-library-list">
          {documents.map((document) => (
            <article className="library-document" key={document.document_id}>
              <span className="file-type-icon"><FileText size={17} /></span>
              <div className="library-document-main">
                <strong>{document.filename}</strong>
                <small>{document.chunk_count} chunks · {formatSize(document.size_bytes)} · {formatDate(document.uploaded_at)}</small>
              </div>
              <button
                type="button"
                className="icon-button small-icon-button"
                aria-label={`Delete ${document.filename}`}
                onClick={() => onDelete(document)}
                disabled={deletingId === document.document_id}
              >{deletingId === document.document_id ? <LoaderCircle size={15} className="spin-icon" /> : <Trash2 size={15} />}</button>
            </article>
          ))}
        </div>
      ) : (
        <p className="documents-empty">No indexed documents yet. Upload a PDF or TXT file above.</p>
      )}
    </section>
  );
}
