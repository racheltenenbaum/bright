import * as Sentry from "@sentry/capacitor";
import * as SentryReact from "@sentry/react";

const DSN = import.meta.env.VITE_SENTRY_DSN;

// No-ops when the DSN isn't set (e.g. local dev) instead of throwing.
export function initErrorMonitoring() {
  if (!DSN) return;
  Sentry.init(
    {
      dsn: DSN,
      // Native crashes (like the Android BroadcastReceiver crash this was
      // added after) happen before any JS runs, so this must be initialized
      // as early as possible in main.jsx — not lazily on first navigation.
      tracesSampleRate: 0.2,
    },
    SentryReact.init,
  );
}

export function identifyErrorMonitoring(user) {
  if (!DSN || !user) return;
  Sentry.setUser({ id: String(user.id), email: user.email });
}

export function resetErrorMonitoring() {
  if (!DSN) return;
  Sentry.setUser(null);
}
