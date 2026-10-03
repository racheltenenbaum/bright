// Decides when a walker in Go mode has really left the planned route, so the
// app can re-plan from where they are. Errs heavily on the side of "still on
// route": a wrong re-plan (route suddenly changing under someone who's fine)
// is worse than noticing a real detour a few seconds later. Every condition
// below has to hold at once:
//
// - Only fixes the GPS itself vouches for: accuracy reported, and no worse
//   than maxAccuracyM. Urban-canyon and indoor fixes are routinely 50m+ off.
// - Clear of the route even giving the GPS the benefit of the doubt: the
//   distance to the route line, minus the fix's accuracy, is still beyond
//   thresholdM. 30m clears the far sidewalk of a wide street (Wiedner
//   Hauptstraße's are 29m apart), so walking on the other side never counts.
// - Sustained: at least minFixes such fixes, spanning at least
//   minDurationMs, with no confidently-on-route fix in between (any one
//   resets the count — e.g. stepping off to let someone pass).
// - Actually moving: at least minMovedM between the first and latest of
//   those fixes, so GPS drift while standing in a shop doesn't count.
//
// Fixes that are neither (poor accuracy, or an error circle that still
// reaches the route) are ignored rather than resetting progress.
export const OFF_ROUTE = {
  thresholdM: 30,
  maxAccuracyM: 35,
  minFixes: 4,
  minDurationMs: 15_000,
  minMovedM: 20,
};

const EARTH_M_PER_DEG = 111_320;

function toXY(lat, lng, refLat) {
  return [lng * Math.cos((refLat * Math.PI) / 180) * EARTH_M_PER_DEG, lat * EARTH_M_PER_DEG];
}

function pointSegmentM([px, py], [ax, ay], [bx, by]) {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

// Meters from (lat, lng) to the nearest point on the route polyline.
export function distanceToRouteM(lat, lng, coords) {
  if (!coords?.length) return Infinity;
  const p = toXY(lat, lng, lat);
  if (coords.length === 1) return pointSegmentM(p, toXY(...coords[0], lat), toXY(...coords[0], lat));
  let best = Infinity;
  for (let i = 0; i < coords.length - 1; i++) {
    best = Math.min(best, pointSegmentM(p, toXY(...coords[i], lat), toXY(...coords[i + 1], lat)));
  }
  return best;
}

function metersBetween(a, b) {
  return pointSegmentM(toXY(a.lat, a.lng, a.lat), toXY(b.lat, b.lng, a.lat), toXY(b.lat, b.lng, a.lat));
}

export function createOffRouteDetector(config = OFF_ROUTE) {
  let streak = [];
  return {
    // fix: { lat, lng, accuracy (m), time (ms) }. True exactly when this fix
    // completes the evidence that the walker has left the route.
    update(fix, coords) {
      if (!coords || coords.length < 2) {
        streak = [];
        return false;
      }
      if (!(fix.accuracy > 0) || fix.accuracy > config.maxAccuracyM) return false;
      const d = distanceToRouteM(fix.lat, fix.lng, coords);
      if (d <= config.thresholdM) {
        streak = [];
        return false;
      }
      if (d - fix.accuracy <= config.thresholdM) return false;

      streak.push(fix);
      const first = streak[0];
      if (
        streak.length >= config.minFixes
        && fix.time - first.time >= config.minDurationMs
        && metersBetween(first, fix) >= config.minMovedM
      ) {
        streak = [];
        return true;
      }
      return false;
    },
    reset() {
      streak = [];
    },
  };
}
