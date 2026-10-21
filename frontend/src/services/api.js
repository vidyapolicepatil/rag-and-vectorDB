const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001"
).replace(/\/+$/, "");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(
      `Cannot reach the backend at ${API_BASE_URL}. Start it in a separate PowerShell window with: cd C:\\Users\\Admin\\Desktop\\ragandvector\\backend; .\\start_backend.ps1. Keep that window open while using the app.`,
    );
  }

  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body.detail || body.message || "";
    } catch {
      // Error responses are not required to contain JSON.
    }
    throw new Error(
      detail || `Backend endpoint ${path} returned HTTP ${response.status}.`,
    );
  }

  if (response.status === 204) return null;
  try {
    return await response.json();
  } catch {
    throw new Error(`Backend endpoint ${path} returned an invalid JSON response.`);
  }
}

export function checkHealth() {
  return request("/health").then((health) => {
    if (health?.status !== "ok" || health?.service !== "research-lens-api") {
      throw new Error(
        `The service at ${API_BASE_URL} is not the Research Lens API. Check VITE_API_BASE_URL.`,
      );
    }
    return health;
  });
}

export function uploadDocument(file) {
  const body = new FormData();
  body.append("file", file);
  return request("/api/upload", {
    method: "POST",
    body,
  });
}

export function listDocuments() {
  return request("/api/documents");
}

export function deleteDocument(documentId) {
  return request(`/api/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
}

export function askQuestion(question, documentId) {
  return request("/api/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question: question,
      document_id: documentId,
      vector_database: "chroma",
    }),
  });
}

export function runRetrievalExperiment(settings) {
  return request("/api/experiments/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export function getExperiments() {
  return request("/api/experiments");
}

export function saveExperimentEvaluations(experimentId, evaluations) {
  return request(`/api/experiments/${encodeURIComponent(experimentId)}/evaluations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ evaluations }),
  });
}

export { API_BASE_URL };
