import { apiClient } from "./client";

export function listMeetings() {
  return apiClient.get("/meetings").then((res) => res.data.meetings);
}

export function getMeeting(id) {
  return apiClient.get(`/meetings/${id}`).then((res) => res.data);
}

export function uploadMeeting({ title, file, onProgress }) {
  const formData = new FormData();
  formData.append("title", title);
  formData.append("file", file);

  return apiClient
    .post("/meetings", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event) => {
        if (onProgress && event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      },
    })
    .then((res) => res.data);
}

export function deleteMeeting(id) {
  return apiClient.delete(`/meetings/${id}`);
}

export function getMeetingStatus(id) {
  return apiClient.get(`/meetings/${id}/status`).then((res) => res.data);
}

export function getTranscript(id) {
  return apiClient.get(`/meetings/${id}/transcript`).then((res) => res.data.segments);
}

export function getSpeakers(id) {
  return apiClient.get(`/meetings/${id}/speakers`).then((res) => res.data.speakers);
}

export function renameSpeaker(id, speakerLabel, displayName) {
  return apiClient
    .patch(`/meetings/${id}/speakers/${encodeURIComponent(speakerLabel)}`, { display_name: displayName })
    .then((res) => res.data);
}

export function getSummary(id) {
  return apiClient.get(`/meetings/${id}/summary`).then((res) => res.data);
}

export function triggerSummarize(id) {
  return apiClient.post(`/meetings/${id}/summarize`).then((res) => res.data);
}

export function getActionItems(id) {
  return apiClient.get(`/meetings/${id}/action-items`).then((res) => res.data.action_items);
}

export function setActionItemCompleted(id, actionItemId, isCompleted) {
  return apiClient
    .patch(`/meetings/${id}/action-items/${actionItemId}`, { is_completed: isCompleted })
    .then((res) => res.data);
}

export function getDecisions(id) {
  return apiClient.get(`/meetings/${id}/decisions`).then((res) => res.data.decisions);
}

export function getQuotes(id) {
  return apiClient.get(`/meetings/${id}/quotes`).then((res) => res.data.quotes);
}

export function downloadReportPdf(id) {
  // The PDF endpoint needs the same Bearer token as every other request, so
  // a plain <a href> can't hit it directly -- fetch as a blob and let the
  // caller turn that into a download (see MeetingDetailPage's handler).
  return apiClient.get(`/meetings/${id}/report.pdf`, { responseType: "blob" }).then((res) => res.data);
}
