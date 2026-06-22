import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { deleteMeeting, listMeetings, uploadMeeting } from "../api/meetings";
import { StatusBadge } from "../components/StatusBadge";

const ACCEPTED_EXTENSIONS = ".wav,.mp3,.mp4,.m4a,.ogg,.oga,.opus,.flac,.webm,.mov,.mkv,.aac";

export function DashboardPage() {
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listMeetings();
      setMeetings(data);
      setLoadError(null);
    } catch {
      setLoadError("Could not load meetings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleUpload(event) {
    event.preventDefault();
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    setProgress(0);
    try {
      await uploadMeeting({ title: title || file.name, file, onProgress: setProgress });
      setTitle("");
      setFile(null);
      event.target.reset();
      await refresh();
    } catch (err) {
      setUploadError(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id) {
    if (!window.confirm("Delete this meeting? This cannot be undone.")) return;
    await deleteMeeting(id);
    await refresh();
  }

  return (
    <div className="dashboard">
      <section className="upload-card">
        <h2>Upload a meeting recording</h2>
        <form onSubmit={handleUpload}>
          <label>
            Title
            <input
              type="text"
              placeholder="e.g. Sprint Planning"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label>
            Audio/video file
            <input
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              onChange={(e) => setFile(e.target.files[0] || null)}
              required
            />
          </label>
          {uploadError && <p className="form-error">{uploadError}</p>}
          {uploading && <progress value={progress} max="100" />}
          <button type="submit" disabled={uploading || !file}>
            {uploading ? `Uploading... ${progress}%` : "Upload"}
          </button>
        </form>
      </section>

      <section className="meetings-list">
        <h2>Your meetings</h2>
        {loading && <p>Loading...</p>}
        {loadError && <p className="form-error">{loadError}</p>}
        {!loading && meetings.length === 0 && (
          <p>No meetings yet. Upload one above to get started.</p>
        )}
        {meetings.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>File</th>
                <th>Uploaded</th>
                <th>Duration</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {meetings.map((meeting) => (
                <tr key={meeting.id}>
                  <td>
                    <Link to={`/meetings/${meeting.id}`}>{meeting.title}</Link>
                  </td>
                  <td>{meeting.original_filename}</td>
                  <td>{new Date(meeting.uploaded_at).toLocaleString()}</td>
                  <td>
                    {meeting.duration_seconds
                      ? `${Math.round(meeting.duration_seconds)}s`
                      : "Pending"}
                  </td>
                  <td>
                    <StatusBadge status={meeting.status} />
                  </td>
                  <td>
                    <button onClick={() => handleDelete(meeting.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
