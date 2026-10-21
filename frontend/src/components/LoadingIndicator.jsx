export default function LoadingIndicator({ label = "Connecting to backend..." }) {
  return (
    <div className="loading-indicator" role="status">
      <span className="loading-spinner" />
      <span>{label}</span>
    </div>
  );
}
