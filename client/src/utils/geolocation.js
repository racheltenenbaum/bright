import { Capacitor } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";

// On native, navigator.geolocation goes through the WebView, and iOS labels
// that prompt with the WebView's origin ("localhost wants to access your
// location"). The Capacitor plugin uses the app-level "bright" prompt, so on
// native we only ever use the plugin and never fall back to the browser API.
const isNative = Capacitor.isNativePlatform();

function browserGetCurrentPosition(options) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation unavailable"));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, options);
  });
}

export async function getCurrentPosition(options = {}) {
  if (isNative) {
    await Geolocation.requestPermissions();
    return Geolocation.getCurrentPosition(options);
  }
  return browserGetCurrentPosition(options);
}

// Returns a function that stops watching.
export function watchPosition(options, onPosition) {
  if (isNative) {
    let id = null;
    let stopped = false;
    Geolocation.requestPermissions()
      .then(() =>
        Geolocation.watchPosition(options, (pos, err) => {
          if (err || !pos) return;
          onPosition(pos.coords.latitude, pos.coords.longitude);
        }),
      )
      .then((watchId) => {
        id = watchId;
        if (stopped) Geolocation.clearWatch({ id }).catch(() => {});
      })
      .catch(() => {});
    return () => {
      stopped = true;
      if (id !== null) Geolocation.clearWatch({ id }).catch(() => {});
    };
  }

  if (!navigator.geolocation) return () => {};
  const id = navigator.geolocation.watchPosition(
    ({ coords }) => onPosition(coords.latitude, coords.longitude),
    null,
    options,
  );
  return () => navigator.geolocation.clearWatch(id);
}
