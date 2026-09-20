import mixpanel from "mixpanel-browser";

const TOKEN = import.meta.env.VITE_MIXPANEL_TOKEN;
let initialized = false;

// No-ops when the token isn't set (e.g. local dev) instead of throwing.
export function initAnalytics() {
  if (!TOKEN || initialized) return;
  // Project is EU-hosted — the default US endpoint accepts events but they
  // never appear in an EU project's dashboard, so this must be explicit.
  mixpanel.init(TOKEN, {
    persistence: "localStorage",
    ignore_dnt: false,
    api_host: "https://api-eu.mixpanel.com",
  });
  initialized = true;
}

export function track(event, props) {
  if (!initialized) return;
  mixpanel.track(event, props);
}

export function identify(user) {
  if (!initialized || !user) return;
  mixpanel.identify(String(user.id));
  mixpanel.people.set({ $email: user.email, $name: user.first_name });
}

export function resetAnalytics() {
  if (!initialized) return;
  mixpanel.reset();
}
