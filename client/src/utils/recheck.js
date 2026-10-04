// Go mode's background recheck: while walking, periodically re-plan the rest
// of the route with the walker's real pace, and switch only if the new route
// is clearly better. The route was planned assuming a pace (see the
// backend's WALKING_SPEED_MPS) to time the sun on each street; a much slower
// or faster walker reaches the far end at a different time, under a
// different sun. Pace is measured as progress *along the route* over time,
// stops included — GPS speed is noisy at walking pace and drops to zero at
// every light, while a coffee stop genuinely delays arrival.
export const RECHECK = {
  intervalMs: 5 * 60_000,       // periodic recheck...
  intervalM: 400,               // ...or after this much walking, whichever first
  driftMs: 10 * 60_000,         // projected arrival this far off plan → recheck now
  minGapMs: 2 * 60_000,         // never recheck more often than this
  minRemainingMs: 10 * 60_000,  // not worth it with less walking left
  nearTurnM: 50,                // don't swap the route right before a turn
  betterBy: 0.15,               // switch only for ≥15 points more preferred sun/shade
  paceWindowMs: 5 * 60_000,
  paceMinSpanMs: 2 * 60_000,
  pausedWindowMs: 2 * 60_000,
  pausedRadiusM: 15,
  defaultSpeedMps: 1.3,
  minSpeedMps: 0.3,             // the backend's accepted range
  maxSpeedMps: 3.0,
  maxFixGapMs: 30_000,          // longer GPS silences don't count as moving time
};

const M_PER_DEG = 111_320;

function toXY([lat, lng], refLat) {
  return [lng * Math.cos((refLat * Math.PI) / 180) * M_PER_DEG, lat * M_PER_DEG];
}

function fromXY([x, y], refLat) {
  return [y / M_PER_DEG, x / (Math.cos((refLat * Math.PI) / 180) * M_PER_DEG)];
}

function metersBetween(a, b) {
  const [ax, ay] = toXY(a, a[0]);
  const [bx, by] = toXY(b, a[0]);
  return Math.hypot(bx - ax, by - ay);
}

// Where the walker is along the route: distance walked along it (to their
// projection on the nearest segment), its total length, which segment they're
// on, and how far to that segment's end (the next waypoint/turn).
export function routeProgress(lat, lng, coords) {
  if (!coords || coords.length < 2) return null;
  const pts = coords.map((c) => toXY(c, lat));
  const [px, py] = toXY([lat, lng], lat);
  let best = null;
  let acc = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, ay] = pts[i];
    const [bx, by] = pts[i + 1];
    const dx = bx - ax;
    const dy = by - ay;
    const len = Math.hypot(dx, dy);
    const t = len === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (len * len)));
    const qx = ax + t * dx;
    const qy = ay + t * dy;
    const d = Math.hypot(px - qx, py - qy);
    if (!best || d < best.d) {
      best = { d, segIdx: i, alongM: acc + t * len, toNextVertexM: (1 - t) * len, proj: [qx, qy] };
    }
    acc += len;
  }
  return {
    alongM: best.alongM, totalM: acc, segIdx: best.segIdx,
    toNextVertexM: best.toNextVertexM, proj: fromXY(best.proj, lat),
  };
}

// The rest of the route from the walker's projected position onward.
export function remainingCoords(lat, lng, coords) {
  const p = routeProgress(lat, lng, coords);
  if (!p) return null;
  return [p.proj, ...coords.slice(p.segIdx + 1)];
}

export function createPaceTracker(cfg = RECHECK) {
  let samples = [];
  let movingMs = 0;
  let lastTime = null;
  const tracker = {
    add(time, alongM, lat, lng) {
      samples.push({ time, alongM, pos: [lat, lng] });
      if (lastTime != null && !tracker.paused(time)) movingMs += Math.min(time - lastTime, cfg.maxFixGapMs);
      lastTime = time;
      const keep = Math.max(cfg.paceWindowMs, cfg.pausedWindowMs) * 2;
      samples = samples.filter((s) => s.time >= time - keep);
    },
    // Meters per second along the route over the recent window, or null
    // until there's enough history.
    pace(now) {
      const recent = samples.filter((s) => s.time >= now - cfg.paceWindowMs);
      if (recent.length < 2) return null;
      const first = recent[0];
      const last = recent[recent.length - 1];
      const span = last.time - first.time;
      if (span < cfg.paceMinSpanMs) return null;
      const mps = (last.alongM - first.alongM) / (span / 1000);
      return Math.min(cfg.maxSpeedMps, Math.max(cfg.minSpeedMps, mps));
    },
    // Hasn't moved beyond a small radius for the whole recent window.
    paused(now) {
      const recent = samples.filter((s) => s.time >= now - cfg.pausedWindowMs);
      if (recent.length < 2 || now - recent[0].time < cfg.pausedWindowMs * 0.9) return false;
      const last = recent[recent.length - 1].pos;
      return recent.every((s) => metersBetween(s.pos, last) <= cfg.pausedRadiusM);
    },
    // Time spent walking (stops excluded), for learning the account's
    // usual pace from a finished walk.
    movingMs() {
      return movingMs;
    },
    reset() {
      samples = [];
      movingMs = 0;
      lastTime = null;
    },
  };
  return tracker;
}

// Why to recheck now ("stale" | "drift" | "interval"), or null not to.
export function decideRecheck(s, cfg = RECHECK) {
  if (s.busy || !s.sunUp || s.paused) return null;
  if (s.toNextTurnM < cfg.nearTurnM) return null;
  if (s.now - s.lastCheckAt < cfg.minGapMs) return null;
  const speed = s.paceMps ?? cfg.defaultSpeedMps;
  const remainingMs = (s.remainingM / speed) * 1000;
  if (remainingMs < cfg.minRemainingMs) return null;
  if (s.stalePlan) return "stale";
  if (s.paceMps != null && Math.abs(s.now + remainingMs - s.expectedArrivalAt) >= cfg.driftMs) return "drift";
  if (s.now - s.lastCheckAt >= cfg.intervalMs || s.walkedSinceCheckM >= cfg.intervalM) return "interval";
  return null;
}

// Share of the route's length in the walker's preferred conditions.
// segments[i] describes coords[i] → coords[i + 1].
export function preferredFraction(coords, segments, preference) {
  if (!coords || coords.length < 2 || !segments?.length) return 0;
  let total = 0;
  let preferred = 0;
  for (let i = 0; i < coords.length - 1; i++) {
    const len = metersBetween(coords[i], coords[i + 1]);
    const seg = segments[i] ?? segments[segments.length - 1];
    total += len;
    if (preference === "shade" ? seg.shaded : !seg.shaded) preferred += len;
  }
  return total > 0 ? preferred / total : 0;
}

export function isClearlyBetter(newFraction, currentFraction, cfg = RECHECK) {
  return newFraction - currentFraction >= cfg.betterBy - 1e-9;
}
