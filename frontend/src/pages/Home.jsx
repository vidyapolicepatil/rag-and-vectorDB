import {
  ArrowRight,
  BookOpenText,
  BrainCircuit,
  Check,
  Database,
  FileSearch,
  FlaskConical,
  MessageSquareText,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";

export default function Dashboard() {
  return (
    <div className="page-stack">
      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <span className="hero-kicker"><Sparkles size={14} /> YOUR AI RESEARCH WORKSPACE</span>
          <h2>Turn research papers into answers you can trace.</h2>
          <p>Bring your documents into one grounded workflow: retrieve the right passages, ask a question, and inspect the sources behind each answer.</p>
          <div className="hero-actions">
            <Link to="/chat" className="button button-primary">Ask your documents <ArrowRight size={16} /></Link>
            <Link to="/experiments" className="button button-secondary">Explore experiments</Link>
          </div>
          <div className="hero-trust"><Check size={15} /> Answers are generated from retrieved document context</div>
        </div>
        <div className="hero-visual" aria-label="Illustration of document retrieval and grounded answer generation">
          <div className="hero-visual-glow" />
          <div className="hero-document-card">
            <span className="hero-doc-icon"><FileSearch size={18} /></span>
            <span><strong>Research document</strong><small>PDF · indexed passages</small></span>
            <span className="hero-doc-check"><Check size={13} /></span>
          </div>
          <div className="hero-flow-line" />
          <div className="hero-core"><BrainCircuit size={28} /><span>RAG</span></div>
          <div className="hero-flow-line lower" />
          <div className="hero-answer-card">
            <span><Database size={15} /> Retrieved context</span>
            <i /><i /><i />
            <small>Evidence-grounded response</small>
          </div>
          <span className="hero-orbit orbit-one" />
          <span className="hero-orbit orbit-two" />
        </div>
      </section>
      <section className="dashboard-facts" aria-label="Project overview">
        <article className="dashboard-fact">
          <span className="fact-icon fact-blue"><FileSearch size={18} /></span>
          <span><strong>8 stages</strong><small>In the RAG pipeline</small></span>
        </article>
        <article className="dashboard-fact">
          <span className="fact-icon fact-purple"><Database size={18} /></span>
          <span><strong>2 approaches</strong><small>ChromaDB and FAISS</small></span>
        </article>
        <article className="dashboard-fact">
          <span className="fact-icon fact-green"><Check size={18} /></span>
          <span><strong>Evidence first</strong><small>Sources stay attached to answers</small></span>
        </article>
      </section>
      <section className="dashboard-next">
        <div className="dashboard-section-title">
          <div><span className="section-kicker">GET STARTED</span><h2>A clear path from document to discovery</h2></div>
          <Link to="/research" className="text-link">Learn the RAG basics <ArrowRight size={15} /></Link>
        </div>
        <div className="dashboard-step-grid">
          <Link className="dashboard-step-card" to="/chat">
            <span className="step-number">01</span>
            <span className="step-card-icon icon-blue"><FileSearch size={19} /></span>
            <strong>Add a research file</strong>
            <small>Upload a PDF or TXT and let the backend index it.</small>
            <ArrowRight className="step-arrow" size={16} />
          </Link>
          <Link className="dashboard-step-card" to="/chat">
            <span className="step-number">02</span>
            <span className="step-card-icon icon-violet"><MessageSquareText size={19} /></span>
            <strong>Ask with confidence</strong>
            <small>Get a response grounded in retrieved passages.</small>
            <ArrowRight className="step-arrow" size={16} />
          </Link>
          <Link className="dashboard-step-card" to="/experiments">
            <span className="step-number">03</span>
            <span className="step-card-icon icon-amber"><FlaskConical size={19} /></span>
            <strong>Compare retrieval</strong>
            <small>Review measured ChromaDB and FAISS results.</small>
            <ArrowRight className="step-arrow" size={16} />
          </Link>
          <Link className="dashboard-step-card" to="/research">
            <span className="step-number">04</span>
            <span className="step-card-icon icon-teal"><BookOpenText size={19} /></span>
            <strong>Explore the concepts</strong>
            <small>Understand chunking, embeddings, and vector search.</small>
            <ArrowRight className="step-arrow" size={16} />
          </Link>
        </div>
      </section>
    </div>
  );
}
