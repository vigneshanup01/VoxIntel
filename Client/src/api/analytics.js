import { apiClient } from "./client";

export function getSpeakerAnalytics({ from, to } = {}) {
  return apiClient.get("/analytics/speakers", { params: { from, to } }).then((res) => res.data);
}
