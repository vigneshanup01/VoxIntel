import { speakerDisplayName } from "../utils/speakers";

function formatTimestamp(seconds) {
  if (seconds == null) return null;
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export function SummaryPanel({
  summary,
  actionItems = [],
  decisions = [],
  quotes = [],
  speakers = [],
  onToggleActionItem,
  onJumpToTimestamp,
  onRegenerate,
  regenerating,
}) {
  if (!summary) {
    return null;
  }

  const displayNameByLabel = new Map(speakers.map((s) => [s.speaker_label, s.display_name]));

  return (
    <section className="summary-panel">
      <div className="summary-panel__header">
        <h2>Summary</h2>
        <button onClick={onRegenerate} disabled={regenerating}>
          {regenerating ? "Regenerating..." : "Regenerate summary"}
        </button>
      </div>

      <p className="summary-panel__executive">{summary.executive_summary}</p>
      {summary.detailed_summary && <p className="summary-panel__detailed">{summary.detailed_summary}</p>}

      {actionItems.length > 0 && (
        <div className="summary-panel__section">
          <h3>Action items</h3>
          <ul className="action-items-list">
            {actionItems.map((item) => (
              <li key={item.id} className="action-items-list__item">
                <label>
                  <input
                    type="checkbox"
                    checked={item.is_completed}
                    onChange={(e) => onToggleActionItem(item, e.target.checked)}
                  />
                  <span className={item.is_completed ? "action-items-list__done" : ""}>{item.description}</span>
                </label>
                {(item.owner || item.due_date) && (
                  <span className="action-items-list__meta">
                    {item.owner && <>Owner: {item.owner}</>}
                    {item.owner && item.due_date && " · "}
                    {item.due_date && <>Due: {item.due_date}</>}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {decisions.length > 0 && (
        <div className="summary-panel__section">
          <h3>Decisions</h3>
          <ul className="decisions-list">
            {decisions.map((decision) => (
              <li key={decision.id}>{decision.description}</li>
            ))}
          </ul>
        </div>
      )}

      {quotes.length > 0 && (
        <div className="summary-panel__section">
          <h3>Notable quotes</h3>
          <ul className="quotes-list">
            {quotes.map((quote) => (
              <li key={quote.id} className={`quotes-list__item quotes-list__item--${quote.category}`}>
                <button
                  type="button"
                  className="quotes-list__timestamp"
                  onClick={() => onJumpToTimestamp(quote.timestamp_seconds)}
                  disabled={quote.timestamp_seconds == null}
                >
                  {formatTimestamp(quote.timestamp_seconds) || "—"}
                </button>
                <span>
                  &ldquo;{quote.quote_text}&rdquo;
                  {quote.speaker_label && (
                    <em> &mdash; {displayNameByLabel.get(quote.speaker_label) || speakerDisplayName(quote.speaker_label)}</em>
                  )}
                  {quote.category === "risk" && <span className="quotes-list__risk-tag">Risk</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
