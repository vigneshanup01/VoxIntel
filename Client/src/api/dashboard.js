import { apiClient } from "./client";

export function getDashboardSummary() {
  return apiClient.get("/dashboard/summary").then((res) => res.data);
}
