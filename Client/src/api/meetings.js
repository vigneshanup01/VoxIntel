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
