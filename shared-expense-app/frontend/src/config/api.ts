// src/config/api.ts
// Centralised API base URL for the frontend.
// In development it falls back to localhost; in production Vite injects VITE_API_BASE_URL.
export const API_BASE_URL =
    (import.meta.env && import.meta.env.VITE_API_BASE_URL) ??
    "http://localhost:8000";
