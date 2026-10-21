import { useRef, useState } from "react";
import { FileText, FileUp, Info, LoaderCircle, X } from "lucide-react";
import { uploadDocument } from "../services/api.js";
import ErrorMessage from "./ErrorMessage.jsx";

const allowedExtensions = /\.(pdf|txt)$/i;

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileUpload({ onUploaded }) {
  const inputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  function addFiles(fileList) {
    const selected = Array.from(fileList || []);
    const invalid = selected.find((file) => !allowedExtensions.test(file.name));
    if (invalid) {
      setError(`${invalid.name}: only PDF and TXT files are supported.`);
      return;
    }
    setError("");
    setSuccess("");
    setFiles((current) => {
      const known = new Set(current.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
      return [
        ...current,
        ...selected.filter((file) => !known.has(`${file.name}:${file.size}:${file.lastModified}`)),
      ];
    });
  }

  async function uploadSelectedFiles() {
    if (!files.length || uploading) return;
    setUploading(true);
    setError("");
    setSuccess("");
    const successful = [];
    let firstError = "";

    for (const file of files) {
      try {
        const document = await uploadDocument(file);
        if (!document?.indexed || !document.document_id) {
          throw new Error(`${file.name}: backend did not confirm document indexing.`);
        }
        successful.push(file);
        onUploaded?.(document);
      } catch (uploadError) {
        firstError ||= uploadError.message;
      }
    }

    if (successful.length) {
      setFiles((current) => current.filter((file) => !successful.includes(file)));
      setSuccess(
        successful.length === 1
          ? `${successful[0].name} was extracted and indexed successfully.`
          : `${successful.length} documents were extracted and indexed successfully.`,
      );
    }
    if (firstError) setError(firstError);
    setUploading(false);
  }

  return (
    <section className="card upload-card">
      <div className="section-heading">
        <div><span className="section-kicker">DOCUMENT LIBRARY</span><h2>Add research documents</h2></div>
        <span className="soft-tag">PDF · TXT</span>
      </div>
      <button
        type="button"
        className={`dropzone${isDragging ? " dragging" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          addFiles(event.dataTransfer.files);
        }}
        disabled={uploading}
      >
        <span className="upload-icon"><FileUp size={22} /></span>
        <strong>Drop files here or <span>browse</span></strong>
        <small>PDF and UTF-8 text files · Files are indexed by the backend</small>
      </button>
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept=".pdf,.txt,application/pdf,text/plain"
        multiple
        onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }}
      />
      {error && <ErrorMessage message={error} onDismiss={() => setError("")} />}
      {success && <div className="upload-success" role="status"><FileText size={16} />{success}</div>}
      {files.length > 0 && (
        <div className="selected-documents">
          {files.map((file, index) => (
            <div className="selected-file" key={`${file.name}-${file.lastModified}-${index}`}>
              <span className="file-type-icon"><FileText size={17} /></span>
              <span className="selected-file-name"><strong>{file.name}</strong><small>{formatSize(file.size)} · ready to upload</small></span>
              <button
                className="icon-button small-icon-button"
                aria-label={`Remove ${file.name}`}
                onClick={() => setFiles((current) => current.filter((item) => item !== file))}
                disabled={uploading}
              ><X size={15} /></button>
            </div>
          ))}
          <button type="button" className="button button-secondary upload-action" onClick={uploadSelectedFiles} disabled={uploading}>
            {uploading
              ? <><LoaderCircle size={16} className="spin-icon" /> Uploading and indexing...</>
              : <><FileUp size={16} /> Upload and index {files.length} {files.length === 1 ? "file" : "files"}</>}
          </button>
        </div>
      )}
      <div className="upload-footnote"><Info size={14} /> Text extraction, chunking, embeddings, and indexing happen on the backend.</div>
    </section>
  );
}
