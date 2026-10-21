import { Bot, UserRound } from "lucide-react";

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";
  return (
    <article className={`chat-message ${isUser ? "user-message" : "assistant-message"}`}>
      <span className={`message-avatar ${isUser ? "user-avatar" : "assistant-avatar"}`}>
        {isUser ? <UserRound size={17} /> : <Bot size={17} />}
      </span>
      <div className="message-content">
        <div className="message-meta"><strong>{isUser ? "You" : "Research Lens assistant"}</strong><span>{message.time}</span></div>
        <p>{message.content}</p>
        {!isUser && message.sources?.length > 0 && (
          <details className="message-sources">
            <summary>Sources ({message.sources.length})</summary>
            <ul>
              {message.sources.map((source, index) => (
                <li key={`${source.chunk_id}-${index}`}>
                  <strong>{source.filename}</strong>
                  {source.page_number ? ` · page ${source.page_number}` : ""}
                  {` · chunk ${source.chunk_id}`}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </article>
  );
}
