import { apiClient } from "./client";

export function signup({ email, password, fullName }) {
  return apiClient
    .post("/auth/signup", { email, password, full_name: fullName })
    .then((res) => res.data);
}

export function login({ email, password }) {
  return apiClient.post("/auth/login", { email, password }).then((res) => res.data);
}

export function getCurrentUser() {
  return apiClient.get("/auth/me").then((res) => res.data);
}
