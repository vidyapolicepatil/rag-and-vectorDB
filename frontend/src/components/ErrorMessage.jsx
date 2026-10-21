import { AlertCircle, X } from "lucide-react";

export default function ErrorMessage({ message, onDismiss }) {
  if (!message) return null;
  return (
    <div className="error-message" role="alert">
      <AlertCircle size={18} />
      <span>{message}</span>
      {onDismiss && <button className="error-dismiss" onClick={onDismiss} aria-label="Dismiss message"><X size={16} /></button>}
    </div>
  );
}
