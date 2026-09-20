import { Capacitor } from "@capacitor/core";
import { GoogleAuth } from "@codetrix-studio/capacitor-google-auth";
import { SignInWithApple } from "@capacitor-community/apple-sign-in";
import api from "../api";

// The native iOS/Android client IDs live in capacitor.config.json (the
// plugin only reads those from JS-passed options on web); this is only
// used to initialize the web (browser) flow.
const GOOGLE_WEB_CLIENT_ID = import.meta.env.VITE_GOOGLE_OAUTH_WEB_CLIENT_ID;
// Apple's native iOS flow authenticates against the app's bundle ID
// automatically (via the Sign In with Apple capability/entitlement) — this
// Services ID is only needed for the web (Services ID) flow.
const APPLE_SERVICES_ID = import.meta.env.VITE_APPLE_OAUTH_SERVICES_ID;
const APPLE_BUNDLE_ID = "com.racheltenenbaum.bright";

let googleInitialized = false;
let gisScriptPromise = null;

// Google's capacitor-google-auth plugin's *web* implementation still uses
// the old gapi.auth2 library, which Google has been sunsetting in favor of
// Identity Services (GIS) — it now throws instead of opening a popup. So on
// web we bypass the plugin entirely and talk to GIS directly; the plugin is
// only used for native iOS/Android, where it wraps the real native SDKs
// (unaffected by the gapi.auth2 issue).
function loadGisScript() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!gisScriptPromise) {
    gisScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.onload = resolve;
      script.onerror = () => {
        gisScriptPromise = null;
        reject(new Error("Failed to load Google Identity Services"));
      };
      document.head.appendChild(script);
    });
  }
  return gisScriptPromise;
}

async function signInWithGoogleWeb() {
  if (!GOOGLE_WEB_CLIENT_ID) throw new Error("Google sign-in is not configured");
  await loadGisScript();
  const idToken = await new Promise((resolve, reject) => {
    // One Tap can silently never call back at all (e.g. a browser that
    // doesn't support FedCM, or Google's exponential cooldown after a user
    // has dismissed it several times) — without a timeout the button would
    // be stuck in "Signing in…" forever in that case.
    const timeout = setTimeout(() => reject(new Error("cancelled")), 10000);
    window.google.accounts.id.initialize({
      client_id: GOOGLE_WEB_CLIENT_ID,
      callback: (response) => {
        clearTimeout(timeout);
        resolve(response.credential);
      },
    });
    window.google.accounts.id.prompt((notification) => {
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        clearTimeout(timeout);
        reject(new Error("cancelled"));
      }
    });
  });
  const res = await api.post("/users/auth/google", { id_token: idToken });
  return res.data;
}

// The plugin requires initialize() before signIn() on native platforms; it
// reads clientId from capacitor.config.json there.
function ensureGoogleInitialized() {
  if (googleInitialized) return;
  GoogleAuth.initialize();
  googleInitialized = true;
}

// Cross-platform cancellation shapes differ (a DOMException on web, a
// plugin error with a code/message on native) — treat anything that isn't
// a clear failure as a silent cancel rather than surfacing an error.
function isUserCancelled(err) {
  const text = `${err?.code || ""} ${err?.message || ""}`.toLowerCase();
  return /cancel|closed|dismiss/.test(text);
}

export async function signInWithGoogle() {
  try {
    if (Capacitor.getPlatform() === "web") {
      return await signInWithGoogleWeb();
    }
    ensureGoogleInitialized();
    const result = await GoogleAuth.signIn();
    const idToken = result.authentication.idToken;
    const res = await api.post("/users/auth/google", { id_token: idToken });
    return res.data;
  } catch (err) {
    if (isUserCancelled(err)) return null;
    throw err;
  }
}

// Apple sign-in isn't offered on Android — no Apple identity exists to
// authenticate against there, and Google requires no equivalent parity.
export function isAppleSignInSupported() {
  return Capacitor.getPlatform() !== "android";
}

export async function signInWithApple() {
  const isNativeIOS = Capacitor.getPlatform() === "ios";
  let result;
  try {
    result = await SignInWithApple.authorize({
      clientId: isNativeIOS ? APPLE_BUNDLE_ID : APPLE_SERVICES_ID,
      redirectURI: `${import.meta.env.VITE_APP_URL || window.location.origin}/`,
      scopes: "email name",
    });
  } catch (err) {
    if (isUserCancelled(err)) return null;
    throw err;
  }
  const idToken = result.response.identityToken;
  const firstName = result.response.givenName || null;
  const res = await api.post("/users/auth/apple", { id_token: idToken, first_name: firstName });
  return res.data;
}
