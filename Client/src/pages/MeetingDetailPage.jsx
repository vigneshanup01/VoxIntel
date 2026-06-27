import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { deleteMeeting, getMeeting, getSpeakers, getTranscript, renameSpeaker } from "../api/meetings";
import { SpeakerStatsPanel } from "../components/SpeakerStatsPanel";
import { StatusBadge } from "../components/StatusBadge";
import { TranscriptView } from "../components/TranscriptView";
import { speakerDisplayName } from "../utils/speakers";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["completed", "failed"]);
const TRANSCRIPT_VISIBLE_STATUSES = new Set(["transcribed", "diarizing", "completed"]);

export function MeetingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [meeting, setMeeting] = useState(null);
  const [segments, setSegments] = useState([]);
  const [speakers, setSpeakers] = useState([]);
  const [error, setError] = useState(null);

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

        if (data.status === "completed") {
          const sp = await getSpeakers(id);
          if (!cancelled) setSpeakers(sp);
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
  }, [id]);

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

      {meeting.status === "completed" && (
        <SpeakerStatsPanel speakers={speakers} onRename={handleRename} />
      )}

      {TRANSCRIPT_VISIBLE_STATUSES.has(meeting.status) && (
        <section className="transcript-section">
          <h2>Transcript</h2>
          <TranscriptView segments={segments} speakers={speakers} />
        </section>
      )}

      <button onClick={handleDelete}>Delete meeting</button>
    </div>
  );
}
