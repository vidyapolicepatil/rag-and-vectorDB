const notes = [
  ["RAG", "Retrieval-Augmented Generation first searches your documents, then asks a language model to answer using the passages it found. This helps keep answers tied to your source material."],
  ["Embeddings", "An embedding converts text into a list of numbers that represents its meaning. Similar ideas tend to have nearby number representations."],
  ["Chunking and overlap", "Chunking breaks a long document into smaller text passages. Overlap repeats a little text at the edge of neighboring chunks so a sentence split near a boundary is less likely to lose its context."],
  ["Semantic search", "Semantic search compares the meaning of a question with the meaning of stored passages. It can find useful text even when the question uses different words."],
  ["Top-k retrieval", "Top-k is the maximum number of passages returned for a question. This project uses top-k 5, so it retrieves up to five passages."],
  ["Vector databases", "A vector database stores embeddings with their text and source details, and searches for vectors that are close to the question embedding."],
  ["ChromaDB and FAISS", "ChromaDB offers a persistent vector database with stored metadata. FAISS is a vector search library; this project saves its index and keeps chunk details in a separate mapping."],
  ["Why chunk size matters", "Small chunks can focus on one detail but may lose surrounding context. Larger chunks keep more context but can include unrelated text. Comparing sizes helps study that trade-off."],
];

export default function ResearchNotes() {
  return (
    <div className="page-stack">
      <section className="page-intro-card">
        <div>
          <span className="section-kicker">RESEARCH NOTES</span>
          <h2>RAG concepts, in simple terms</h2>
          <p>Short explanations to help describe the document question-answering workflow.</p>
        </div>
      </section>
      <section className="research-notes-list">
        {notes.map(([title, explanation], index) => (
          <article className="research-note" key={title}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div><h3>{title}</h3><p>{explanation}</p></div>
          </article>
        ))}
      </section>
    </div>
  );
}
