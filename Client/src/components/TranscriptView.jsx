import { speakerColor, speakerDisplayName } from "../utils/speakers";

function formatTimestamp(seconds) {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export function TranscriptView({ segments, speakers = [], highlightedSegmentId = null }) {
  if (segments.length === 0) {
    return <p>No speech was detected in this recording.</p>;
  }

  const displayNameByLabel = new Map(speakers.map((s) => [s.speaker_label, s.display_name]));

  return (
    <ol className="transcript">
      {segments.map((segment) => (
        <li
          key={segment.id}
          id={`segment-${segment.id}`}
          className={
            segment.id === highlightedSegmentId
              ? "transcript__segment transcript__segment--highlighted"
              : "transcript__segment"
          }
        >
          <span className="transcript__time">{formatTimestamp(segment.start_time)}</span>
          <span className="transcript__text">
            {segment.speaker_label && (
              <strong
                className="transcript__speaker"
                style={{ color: speakerColor(segment.speaker_label) }}
              >
                {displayNameByLabel.get(segment.speaker_label) || speakerDisplayName(segment.speaker_label)}:{" "}
              </strong>
            )}
            {segment.text}
          </span>
        </li>
      ))}
    </ol>
  );
}
