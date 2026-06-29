const STATUS_LABELS = {
  uploaded: "Uploaded",
  processing: "Processing",
  transcribed: "Transcribed",
  diarizing: "Identifying speakers",
  diarized: "Diarized",
  summarizing: "Summarizing",
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
