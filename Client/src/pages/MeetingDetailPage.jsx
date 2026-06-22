import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { deleteMeeting, getMeeting } from "../api/meetings";
import { StatusBadge } from "../components/StatusBadge";

export function MeetingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [meeting, setMeeting] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getMeeting(id)
      .then(setMeeting)
      .catch(() => setError("Meeting not found."));
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
      </dl>
      <section className="future-slot">
        <h2>Transcript &amp; summary</h2>
        <p>
          Processing hasn&apos;t started yet -- transcription, speaker diarization, emotion
          detection, and summaries arrive in later phases.
        </p>
      </section>
      <button onClick={handleDelete}>Delete meeting</button>
    </div>
  );
}
