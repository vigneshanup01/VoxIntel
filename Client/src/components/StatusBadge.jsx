const STATUS_LABELS = {
  uploaded: "Uploaded",
  processing: "Processing",
  transcribed: "Transcribed",
  completed: "Completed",
  failed: "Failed",
};

export function StatusBadge({ status }) {
  return (
    <span className={`status-badge status-badge--${status}`}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}
