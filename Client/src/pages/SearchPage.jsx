import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { searchMeetings, searchTranscripts } from "../api/search";
import { StatusBadge } from "../components/StatusBadge";

const DEBOUNCE_MS = 350;

function formatTimestamp(seconds) {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

function highlightMatch(text, term) {
  if (!term) return text;
  const index = text.toLowerCase().indexOf(term.toLowerCase());
  if (index === -1) return text;
  return (
    <>
      {text.slice(0, index)}
      <mark>{text.slice(index, index + term.length)}</mark>
      {text.slice(index + term.length)}
    </>
  );
}

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [speaker, setSpeaker] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [meetings, setMeetings] = useState([]);
  const [transcriptResults, setTranscriptResults] = useState([]);
  const [searched, setSearched] = useState(false);
  const debounceRef = useRef(null);

  const runSearch = useCallback(async (q, spk, from, to) => {
    const meetingsPromise = searchMeetings({
      q: q || undefined,
      speaker: spk || undefined,
      from: from || undefined,
      to: to || undefined,
    });
    const transcriptsPromise = q ? searchTranscripts({ q }) : Promise.resolve({ results: [] });
    const [meetingsData, transcriptsData] = await Promise.all([meetingsPromise, transcriptsPromise]);
    setMeetings(meetingsData.meetings);
    setTranscriptResults(transcriptsData.results);
    setSearched(true);
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      runSearch(query, speaker, dateFrom, dateTo);
    }, DEBOUNCE_MS);
    return () => clearTimeout(debounceRef.current);
  }, [query, speaker, dateFrom, dateTo, runSearch]);

  return (
    <div className="search-page">
      <h1>Search</h1>
      <div className="search-filters">
        <input
          type="text"
          placeholder="Search titles and transcripts..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <input
          type="text"
          placeholder="Speaker name"
          value={speaker}
          onChange={(e) => setSpeaker(e.target.value)}
        />
        <label>
          From
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
      </div>

      <section className="search-results">
        <h2>Meetings ({meetings.length})</h2>
        {searched && meetings.length === 0 && <p>No meetings match.</p>}
        {meetings.length > 0 && (
          <ul className="search-meeting-list">
            {meetings.map((meeting) => (
              <li key={meeting.id}>
                <Link to={`/meetings/${meeting.id}`}>{meeting.title}</Link>
                <StatusBadge status={meeting.status} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {query && (
        <section className="search-results">
          <h2>Transcript matches ({transcriptResults.length})</h2>
          {searched && transcriptResults.length === 0 && <p>No transcript matches.</p>}
          {transcriptResults.length > 0 && (
            <ul className="search-transcript-list">
              {transcriptResults.map((result) => (
                <li key={result.segment_id}>
                  <Link to={`/meetings/${result.meeting_id}?t=${result.start_time}`}>
                    {result.meeting_title} &middot; {formatTimestamp(result.start_time)}
                  </Link>
                  <p>{highlightMatch(result.snippet, query)}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
