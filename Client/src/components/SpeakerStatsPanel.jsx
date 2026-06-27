import { speakerColor, speakerDisplayName } from "../utils/speakers";

export function SpeakerStatsPanel({ speakers, onRename }) {
  if (speakers.length === 0) {
    return null;
  }

  return (
    <section className="speaker-stats">
      <h2>Speakers</h2>
      <ul className="speaker-bar-list">
        {speakers.map((speaker) => (
          <li key={speaker.speaker_label} className="speaker-bar-row">
            <span className="speaker-bar-label" style={{ color: speakerColor(speaker.speaker_label) }}>
              {speakerDisplayName(speaker)}
            </span>
            <div className="speaker-bar-track">
              <div
                className="speaker-bar-fill"
                style={{
                  width: `${Math.min(100, speaker.speaking_percentage)}%`,
                  background: speakerColor(speaker.speaker_label),
                }}
              />
            </div>
            <span className="speaker-bar-meta">
              {speaker.speaking_percentage.toFixed(0)}% &middot; {speaker.turn_count}{" "}
              {speaker.turn_count === 1 ? "turn" : "turns"}
            </span>
            <button onClick={() => onRename(speaker)}>Rename</button>
          </li>
        ))}
      </ul>
    </section>
  );
}
