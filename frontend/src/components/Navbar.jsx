import { useLocation } from "react-router-dom";

const titles = {
  "/": ["Dashboard", "Your document research workspace."],
  "/chat": ["Ask your documents", "Find answers grounded in your research files."],
  "/experiments": ["Experiments", "Compare ChromaDB and FAISS with measured results."],
  "/research": ["Research Notes", "A simple guide to the RAG workflow."],
};

export default function Navbar() {
  const { pathname } = useLocation();
  const [title, subtitle] = titles[pathname] || titles["/"];

  return (
    <header className="topbar">
      <div className="topbar-heading">
        <span className="eyebrow">RESEARCH LENS</span>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
    </header>
  );
}
