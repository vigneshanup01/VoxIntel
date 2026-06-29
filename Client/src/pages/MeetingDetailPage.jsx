import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  deleteMeeting,
  downloadReportPdf,
  getActionItems,
  getDecisions,
  getMeeting,
  getQuotes,
  getSpeakers,
  getSummary,
  getTranscript,
  renameSpeaker,
  setActionItemCompleted,
  triggerSummarize,
} from "../api/meetings";
import { SpeakerStatsPanel } from "../components/SpeakerStatsPanel";
import { StatusBadge } from "../components/StatusBadge";
import { SummaryPanel } from "../components/SummaryPanel";
import { TranscriptView } from "../components/TranscriptView";
import { speakerDisplayName } from "../utils/speakers";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["completed", "failed"]);
const TRANSCRIPT_VISIBLE_STATUSES = new Set(["transcribed", "diarizing", "diarized", "summarizing", "completed"]);
const SPEAKERS_VISIBLE_STATUSES = new Set(["diarized", "summarizing", "completed"]);
const BUSY_STATUSES = new Set(["uploaded", "processing", "diarizing", "diarized", "summarizing"]);

export function MeetingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [meeting, setMeeting] = useState(null);
  const [segments, setSegments] = useState([]);
  const [speakers, setSpeakers] = useState([]);
  const [summary, setSummary] = useState(null);
  const [actionItems, setActionItems] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [quotes, setQuotes] = useState([]);
  const [highlightedSegmentId, setHighlightedSegmentId] = useState(null);
  const [error, setError] = useState(null);
  const [pollKey, setPollKey] = useState(0);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [appliedJumpParam, setAppliedJumpParam] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let intervalId;

    async function poll() {
      try {
        const data = await getMeeting(id);
        if (cancelled) return;
        setMeeting(data);

        if (TRANSCRIPT_VISIBLE_STATUSES.has(data.status)) {
          // Refetched every tick (not just once): speaker_label on each
          // segment only gets filled in once diarization finishes, so an
          // earlier fetch (while still "transcribed") would otherwise be
          // permanently missing it.
          const segs = await getTranscript(id);
          if (!cancelled) setSegments(segs);
        }

        if (SPEAKERS_VISIBLE_STATUSES.has(data.status)) {
          const sp = await getSpeakers(id);
          if (!cancelled) setSpeakers(sp);
        }

        if (data.status === "completed") {
          try {
            const [sum, items, dec, qts] = await Promise.all([
              getSummary(id),
              getActionItems(id),
              getDecisions(id),
              getQuotes(id),
            ]);
            if (!cancelled) {
              setSummary(sum);
              setActionItems(items);
              setDecisions(dec);
              setQuotes(qts);
            }
          } catch {
            // Summary endpoints 404 until the first summarization run has
            // saved anything -- not a page-level error.
          }
        }

        if (TERMINAL_STATUSES.has(data.status)) {
          clearInterval(intervalId);
        }
      } catch {
        if (!cancelled) setError("Meeting not found.");
        clearInterval(intervalId);
      }
    }

    poll();
    intervalId = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [id, pollKey]);

  async function handleDelete() {
    if (!window.confirm("Delete this meeting? This cannot be undone.")) return;
    await deleteMeeting(id);
    navigate("/");
  }

  async function handleRename(speaker) {
    const next = window.prompt(`Rename ${speakerDisplayName(speaker)} to:`, speaker.display_name || "");
    if (next === null) return;
    const updated = await renameSpeaker(id, speaker.speaker_label, next.trim() || null);
    setSpeakers((prev) => prev.map((s) => (s.speaker_label === updated.speaker_label ? updated : s)));
  }

  async function handleGenerateSummary() {
    try {
      const updated = await triggerSummarize(id);
      setMeeting(updated);
      // This moves the meeting off its terminal status, so the polling
      // effect's interval (cleared once terminal) needs restarting.
      setPollKey((key) => key + 1);
    } catch {
      setError("Could not start summarization.");
    }
  }

  async function handleToggleActionItem(item, isCompleted) {
    const updated = await setActionItemCompleted(id, item.id, isCompleted);
    setActionItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
  }

  function handleJumpToTimestamp(seconds) {
    if (seconds == null || segments.length === 0) return;
    let nearest = segments[0];
    let bestDiff = Math.abs(segments[0].start_time - seconds);
    for (const segment of segments) {
      const diff = Math.abs(segment.start_time - seconds);
      if (diff < bestDiff) {
        bestDiff = diff;
        nearest = segment;
      }
    }
    setHighlightedSegmentId(nearest.id);
    document.getElementById(`segment-${nearest.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => {
      setHighlightedSegmentId((current) => (current === nearest.id ? null : current));
    }, 2000);
  }

  // Supports links like /meetings/{id}?t=42.5 from the search page's
  // "jump to this point" transcript results -- applies once, the first
  // time segments are available, not on every poll tick.
  useEffect(() => {
    const t = searchParams.get("t");
    if (!appliedJumpParam && t && segments.length > 0) {
      handleJumpToTimestamp(parseFloat(t));
      setAppliedJumpParam(true);
    }
  }, [searchParams, segments, appliedJumpParam]);

  async function handleDownloadReport() {
    setDownloadingReport(true);
    try {
      const blob = await downloadReportPdf(id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${meeting.title}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not download the report.");
    } finally {
      setDownloadingReport(false);
    }
  }

  if (error) {
    return (
      <div className="meeting-detail">
        <p className="form-error">{error}</p>
        <Link to="/">Back to dashboard</Link>
      </div>
    );
  }

  if (!meeting) {
    return <p>Loading...</p>;
  }

  return (
    <div className="meeting-detail">
      <Link to="/">&larr; Back to dashboard</Link>
      <h1>{meeting.title}</h1>
      <StatusBadge status={meeting.status} />
      <dl>
        <dt>Original filename</dt>
        <dd>{meeting.original_filename}</dd>
        <dt>Uploaded</dt>
        <dd>{new Date(meeting.uploaded_at).toLocaleString()}</dd>
        <dt>Duration</dt>
        <dd>
          {meeting.duration_seconds
            ? `${Math.round(meeting.duration_seconds)}s`
            : "Pending processing"}
        </dd>
        {meeting.language_detected && (
          <>
            <dt>Detected language</dt>
            <dd>{meeting.language_detected}</dd>
          </>
        )}
      </dl>

      {meeting.status === "failed" && (
        <p className="form-error">
          Processing failed: {meeting.processing_error || "An unknown error occurred."}
        </p>
      )}

      {!summary && !BUSY_STATUSES.has(meeting.status) && segments.length > 0 && (
        <p className="transcript-status">
          <span>No summary yet for this meeting.</span>
          <button onClick={handleGenerateSummary}>Generate summary</button>
        </p>
      )}

      {(meeting.status === "uploaded" || meeting.status === "processing") && (
        <p className="transcript-status">
          <span className="spinner" aria-hidden="true" />
          <span>
            {meeting.processing_progress || "Transcribing this recording..."}
            <span className="transcript-status__hint">
              {" "}
              this can take a minute or two depending on length
            </span>
          </span>
        </p>
      )}

      {meeting.status === "diarizing" && (
        <p className="transcript-status">
          <span className="spinner" aria-hidden="true" />
          <span>{meeting.processing_progress || "Identifying speakers..."}</span>
        </p>
      )}

      {meeting.status === "diarized" && (
        <p className="transcript-status">
          <span className="spinner" aria-hidden="true" />
          <span>Queued for summarization...</span>
        </p>
      )}

      {meeting.status === "summarizing" && !summary && (
        <p className="transcript-status">
          <span className="spinner" aria-hidden="true" />
          <span>{meeting.processing_progress || "Generating summary..."}</span>
        </p>
      )}

      {SPEAKERS_VISIBLE_STATUSES.has(meeting.status) && (
        <SpeakerStatsPanel speakers={speakers} onRename={handleRename} />
      )}

      {summary && (
        <SummaryPanel
          summary={summary}
          actionItems={actionItems}
          decisions={decisions}
          quotes={quotes}
          speakers={speakers}
          onToggleActionItem={handleToggleActionItem}
          onJumpToTimestamp={handleJumpToTimestamp}
          onRegenerate={handleGenerateSummary}
          regenerating={meeting.status === "summarizing"}
        />
      )}

      {summary && (
        <button onClick={handleDownloadReport} disabled={downloadingReport}>
          {downloadingReport ? "Preparing report..." : "Download report (PDF)"}
        </button>
      )}

      {TRANSCRIPT_VISIBLE_STATUSES.has(meeting.status) && (
        <section className="transcript-section">
          <h2>Transcript</h2>
          <TranscriptView segments={segments} speakers={speakers} highlightedSegmentId={highlightedSegmentId} />
        </section>
      )}

      <button onClick={handleDelete}>Delete meeting</button>
    </div>
  );
}
