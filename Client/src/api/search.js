import { apiClient } from "./client";

export function searchMeetings({ q, speaker, from, to, limit = 20, offset = 0 } = {}) {
  return apiClient
    .get("/meetings/search", { params: { q, speaker, from, to, limit, offset } })
    .then((res) => res.data);
}

export function searchTranscripts({ q, limit = 20, offset = 0 } = {}) {
  return apiClient.get("/search/transcripts", { params: { q, limit, offset } }).then((res) => res.data);
}
