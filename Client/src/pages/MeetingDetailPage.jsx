import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { deleteMeeting, getMeeting, getTranscript } from "../api/meetings";
import { StatusBadge } from "../components/StatusBadge";
import { TranscriptView } from "../components/TranscriptView";

const POLL_INTERVAL_MS = 3000;
const ACTIVE_STATUSES = new Set(["uploaded", "processing"]);
const TRANSCRIBED_STATUSES = new Set(["transcribed", "completed"]);

export function MeetingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [meeting, setMeeting] = useState(null);
  const [segments, setSegments] = useState([]);
  const [error, setError] = useState(null);
  const segmentsLoadedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let intervalId;

    async function poll() {
      try {
        const data = await getMeeting(id);
        if (cancelled) return;
        setMeeting(data);

        if (TRANSCRIBED_STATUSES.has(data.status) && !segmentsLoadedRef.current) {
          segmentsLoadedRef.current = true;
          const segs = await getTranscript(id);
          if (!cancelled) setSegments(segs);
        }

        if (!ACTIVE_STATUSES.has(data.status)) {
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

      <section className="transcript-section">
        <h2>Transcript</h2>
        {ACTIVE_STATUSES.has(meeting.status) && (
          <p className="transcript-status">
            <span className="spinner" aria-hidden="true" />
            Transcribing this recording... this can take a minute or two depending on length.
          </p>
        )}
        {meeting.status === "failed" && (
          <p className="form-error">
            Transcription failed: {meeting.processing_error || "An unknown error occurred."}
          </p>
        )}
        {TRANSCRIBED_STATUSES.has(meeting.status) && <TranscriptView segments={segments} />}
      </section>

      <button onClick={handleDelete}>Delete meeting</button>
    </div>
  );
}
