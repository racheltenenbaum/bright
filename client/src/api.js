import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});

// A 401 here always means "not actually logged in" (missing, expired, or
// otherwise invalid token) — every authenticated screen was previously left
// to fail this individually with whatever generic error it happened to show
// (e.g. route planning surfaced "Could not fetch route", giving no hint the
// real issue was just being logged out). Clearing the session and sending
// the user to /login makes that failure mode self-explanatory everywhere at
// once, instead of screen-by-screen.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export default api;
