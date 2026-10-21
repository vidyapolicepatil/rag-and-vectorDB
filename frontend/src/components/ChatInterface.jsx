import { useRef } from "react";
import { ArrowUp, Bot, Info, RotateCcw } from "lucide-react";
import ChatMessage from "./ChatMessage.jsx";
import ErrorMessage from "./ErrorMessage.jsx";
import LoadingIndicator from "./LoadingIndicator.jsx";

export default function ChatInterface({
  messages,
  question,
  setQuestion,
  loading,
  error,
  onDismissError,
  onSubmit,
  onClear,
  messagesEndRef: suppliedMessagesEndRef,
  emptyMessage,
  loadingLabel = "Retrieving relevant passages and generating an answer...",
}) {
  const localMessagesEndRef = useRef(null);
  const messagesEndRef = suppliedMessagesEndRef || localMessagesEndRef;

  return (
    <section className="card conversation-card">
      <div className="section-heading conversation-heading">
        <div><span className="section-kicker">CONVERSATION</span><h2>Ask your documents</h2></div>
        {messages.length > 0 && <button type="button" className="button button-quiet reset-chat" onClick={onClear} disabled={loading}><RotateCcw size={15} /> Clear conversation</button>}
      </div>
      <div className="conversation-body">
        {messages.length ? (
          <div className="message-list">
            {messages.map((message, index) => <ChatMessage key={`${message.time}-${index}`} message={message} />)}
            {loading && <LoadingIndicator label={loadingLabel} />}
            <div ref={messagesEndRef} />
          </div>
        ) : (
          <div className="chat-welcome">
            <span className="chat-welcome-icon"><Bot size={25} /></span>
            <h3>Start with a question</h3>
            <p>{emptyMessage || "Upload a document, then ask a question about its contents."}</p>
            <span className="backend-needed"><Info size={14} /> Answers require a working backend and configured Groq key</span>
          </div>
        )}
      </div>
      <ErrorMessage message={error} onDismiss={onDismissError} />
      <form className="question-form" onSubmit={onSubmit}>
        <label htmlFor="question-input" className="visually-hidden">Ask a question about your documents</label>
        <textarea
          id="question-input"
          rows="1"
          placeholder="Ask a question about your documents..."
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit(event);
            }
          }}
        />
        <button className="send-button ask-button" type="submit" disabled={loading || !question.trim()}><ArrowUp size={17} /> Ask</button>
        <div className="question-hint"><span>Enter to send · Shift + Enter for a new line</span></div>
      </form>
    </section>
  );
}
