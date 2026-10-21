import { useCallback, useEffect, useRef, useState } from "react";
import FileUpload from "../components/FileUpload.jsx";
import ChatInterface from "../components/ChatInterface.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import DocumentList from "../components/DocumentList.jsx";
import { askQuestion, deleteDocument, listDocuments } from "../services/api.js";

function currentTime() {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date());
}

export default function Chat() {
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const refreshDocuments = useCallback(async (preferredDocumentId = "") => {
    setDocumentsLoading(true);
    setDocumentsError("");
    try {
      const response = await listDocuments();
      if (!Array.isArray(response?.documents)) {
        throw new Error("The backend returned an invalid document list.");
      }
      setDocuments(response.documents);
      const preferredExists = response.documents.some((item) => item.document_id === preferredDocumentId);
      setSelectedDocumentId((current) => (
        preferredExists
          ? preferredDocumentId
          : response.documents.some((item) => item.document_id === current)
            ? current
            : response.documents[0]?.document_id || ""
      ));
    } catch (requestError) {
      setDocumentsError(requestError.message);
    } finally {
      setDocumentsLoading(false);
    }
  }, []);

  useEffect(() => { refreshDocuments(); }, [refreshDocuments]);

  async function removeDocument(document) {
    setDeletingId(document.document_id);
    setDeleteError("");
    try {
      await deleteDocument(document.document_id);
      const remaining = documents.filter((item) => item.document_id !== document.document_id);
      setDocuments(remaining);
      if (selectedDocumentId === document.document_id) {
        setSelectedDocumentId(remaining[0]?.document_id || "");
      }
    } catch (requestError) {
      setDeleteError(requestError.message);
    } finally {
      setDeletingId("");
    }
  }

  async function sendQuestion(event) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    if (!selectedDocumentId) {
      setError("Upload a document or select an indexed document before asking a question.");
      return;
    }

    setError("");
    setQuestion("");
    setMessages((current) => [...current, { role: "user", content: trimmed, time: currentTime() }]);
    setLoading(true);
    try {
      const result = await askQuestion(trimmed, selectedDocumentId);
      if (typeof result?.answer !== "string" || !result.answer.trim()) {
        throw new Error("The backend response did not include an answer.");
      }
      setMessages((current) => [...current, {
        role: "assistant",
        content: result.answer,
        time: currentTime(),
        sources: Array.isArray(result.sources) ? result.sources : [],
      }]);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
      requestAnimationFrame(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }));
    }
  }

  return (
    <div className="page-stack">
      <section className="page-intro-card">
        <div><span className="section-kicker">ASK DOCUMENTS</span><h2>Ask your documents</h2><p>Find answers grounded in your research files.</p></div>
      </section>
      <FileUpload onUploaded={(document) => refreshDocuments(document.document_id)} />
      {deleteError && <ErrorMessage message={deleteError} onDismiss={() => setDeleteError("")} />}
      <DocumentList
        documents={documents}
        loading={documentsLoading}
        error={documentsError}
        onDelete={removeDocument}
        deletingId={deletingId}
      />
      <section className="document-picker">
        <label htmlFor="chat-document">Document for this question</label>
        <select
          id="chat-document"
          value={selectedDocumentId}
          onChange={(event) => setSelectedDocumentId(event.target.value)}
          disabled={documentsLoading || documents.length === 0}
        >
          {documents.length === 0
            ? <option value="">No indexed documents</option>
            : documents.map((document) => (
              <option value={document.document_id} key={document.document_id}>{document.filename}</option>
            ))}
        </select>
      </section>
      <ChatInterface
        messages={messages}
        question={question}
        setQuestion={setQuestion}
        loading={loading}
        error={error}
        onDismissError={() => setError("")}
        onSubmit={sendQuestion}
        onClear={() => { setMessages([]); setError(""); }}
        messagesEndRef={messagesEndRef}
        emptyMessage={documents.length ? "Ask a question about the selected document. Retrieved source details appear under each answer." : "Upload a PDF or TXT document above. Answers require indexed document content and a configured Groq API key."}
        loadingLabel={documentsLoading ? "Loading indexed documents..." : undefined}
      />
    </div>
  );
}
