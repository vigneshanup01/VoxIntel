import { useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { getSpeakerAnalytics } from "../api/analytics";

export function AnalyticsPage() {
  const [speakers, setSpeakers] = useState([]);
  const [unnamedCount, setUnnamedCount] = useState(0);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    const data = await getSpeakerAnalytics({ from: dateFrom || undefined, to: dateTo || undefined });
    setSpeakers(data.speakers.map((s) => ({ ...s, minutes: Math.round(s.total_speaking_seconds / 60) })));
    setUnnamedCount(data.unnamed_speaker_rows_excluded);
    setLoading(false);
  }, [dateFrom, dateTo]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="analytics-page">
      <h1>Speaker analytics</h1>
      <div className="search-filters">
        <label>
          From
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
      </div>

      {loading && <p>Loading...</p>}

      {!loading && speakers.length === 0 && (
        <p>
          No named speakers yet. Rename a speaker from "SPEAKER_00" to a real name on a meeting's detail page to see
          them here -- cross-meeting totals only make sense once a label has been confirmed to be the same person.
        </p>
      )}

      {speakers.length > 0 && (
        <div className="analytics-chart">
          <ResponsiveContainer width="100%" height={Math.max(200, speakers.length * 50)}>
            <BarChart data={speakers} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" unit="m" />
              <YAxis type="category" dataKey="display_name" width={120} />
              <Tooltip formatter={(value) => [`${value} min`, "Speaking time"]} />
              <Bar dataKey="minutes" fill="#2f5fff" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {unnamedCount > 0 && (
        <p className="transcript-status__hint">
          {unnamedCount} speaker record{unnamedCount === 1 ? "" : "s"} excluded from these totals -- no display name
          set, so they can't be reliably matched to a person across meetings.
        </p>
      )}
    </div>
  );
}
