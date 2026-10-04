import { test } from "node:test";
import assert from "node:assert/strict";
import {
  RECHECK,
  createPaceTracker,
  decideRecheck,
  isClearlyBetter,
  preferredFraction,
  remainingCoords,
  routeProgress,
} from "./recheck.js";

const M_LAT = 1 / 111_320;
const M_LNG = 1 / (111_320 * Math.cos((48.2 * Math.PI) / 180));
const at = (x, y) => [48.2 + y * M_LAT, 16.37 + x * M_LNG];
const near = (a, b, tol = 0.5) => Math.abs(a - b) <= tol;

// 1km north, then 500m east.
const ROUTE = [at(0, 0), at(0, 1000), at(500, 1000)];
const MIN = 60_000;

// --- progress along the route ---------------------------------------------

test("progress projects onto the route line", () => {
  const p = routeProgress(...at(5, 400), ROUTE);
  assert.ok(near(p.alongM, 400));
  assert.ok(near(p.totalM, 1500));
  assert.equal(p.segIdx, 0);
  assert.ok(near(p.toNextVertexM, 600));
});

test("progress on a later leg", () => {
  const p = routeProgress(...at(200, 1003), ROUTE);
  assert.ok(near(p.alongM, 1200));
  assert.equal(p.segIdx, 1);
  assert.ok(near(p.toNextVertexM, 300));
});

test("progress handles degenerate routes", () => {
  assert.equal(routeProgress(...at(0, 0), null), null);
  assert.equal(routeProgress(...at(0, 0), [at(0, 0)]), null);
  const p = routeProgress(...at(0, 0), [at(0, 0), at(0, 0), at(0, 100)]);
  assert.ok(near(p.alongM, 0));
});

test("remaining route starts at the walker's projected position", () => {
  const rest = remainingCoords(...at(4, 400), ROUTE);
  assert.equal(rest.length, 3);
  assert.ok(near(rest[0][0], at(0, 400)[0], 1e-6));
  assert.ok(near(rest[0][1], at(0, 400)[1], 1e-6));
  assert.deepEqual(rest.slice(1), ROUTE.slice(1));
  assert.equal(remainingCoords(...at(0, 0), null), null);
});

// --- pace -----------------------------------------------------------------

function walk(tracker, mps, fromS, toS, startAlong = 0, stepS = 10) {
  for (let s = fromS; s <= toS; s += stepS) {
    const along = startAlong + (s - fromS) * mps;
    tracker.add(s * 1000, along, ...at(0, along));
  }
}

test("pace is progress along the route over the recent window", () => {
  const t = createPaceTracker();
  walk(t, 0.5, 0, 600);
  assert.ok(near(t.pace(600_000), 0.5, 0.01));
});

test("pace needs enough history", () => {
  const t = createPaceTracker();
  walk(t, 1.3, 0, 60);
  assert.equal(t.pace(60_000), null);
});

test("pace only looks at the recent window", () => {
  const t = createPaceTracker();
  walk(t, 1.4, 0, 600);           // brisk for 10 minutes...
  walk(t, 0.5, 610, 1200, 840);   // ...then slow for 10
  assert.ok(near(t.pace(1_200_000), 0.5, 0.02));
});

test("pace counts stops and is clamped to the supported range", () => {
  const t = createPaceTracker();
  for (let s = 0; s <= 300; s += 10) t.add(s * 1000, 0, ...at(0, 0));
  assert.equal(t.pace(300_000), RECHECK.minSpeedMps);
  const fast = createPaceTracker();
  walk(fast, 10, 0, 300);
  assert.equal(fast.pace(300_000), RECHECK.maxSpeedMps);
});

test("standing still is detected from position, after long enough", () => {
  const t = createPaceTracker();
  walk(t, 1.3, 0, 300);
  const stopAt = 300 * 1.3;
  for (let s = 310; s <= 500; s += 10) t.add(s * 1000, stopAt, ...at((s % 20) / 10, stopAt));
  assert.equal(t.paused(400_000), false); // only ~90s stopped so far
  assert.equal(t.paused(500_000), true);
  walk(t, 1.3, 510, 560, stopAt);
  assert.equal(t.paused(560_000), false);
});

test("not paused without enough history", () => {
  const t = createPaceTracker();
  t.add(0, 0, ...at(0, 0));
  assert.equal(t.paused(30_000), false);
});

// --- when to recheck ------------------------------------------------------

const base = {
  now: 30 * MIN,
  lastCheckAt: 27 * MIN,
  walkedSinceCheckM: 100,
  remainingM: 2000,
  paceMps: 1.3,
  expectedArrivalAt: 30 * MIN + (2000 / 1.3) * 1000,
  paused: false,
  toNextTurnM: 200,
  sunUp: true,
  busy: false,
  stalePlan: false,
};

test("on schedule and recently checked: no recheck", () => {
  assert.equal(decideRecheck(base), null);
});

test("periodic recheck every 5 minutes", () => {
  assert.equal(decideRecheck({ ...base, lastCheckAt: base.now - RECHECK.intervalMs }), "interval");
});

test("periodic recheck every 400m", () => {
  assert.equal(decideRecheck({ ...base, walkedSinceCheckM: RECHECK.intervalM }), "interval");
});

test("slow walker falling 10+ minutes behind triggers a recheck", () => {
  // 300m in 10 minutes on a 3km walk.
  const slow = { ...base, paceMps: 0.5, remainingM: 2700, expectedArrivalAt: base.now + 20 * MIN };
  assert.equal(decideRecheck(slow), "drift");
});

test("fast walker getting well ahead triggers a recheck too", () => {
  const fast = { ...base, paceMps: 2.0, remainingM: 2400, expectedArrivalAt: base.now + 32 * MIN };
  assert.equal(decideRecheck(fast), "drift");
});

test("small drift doesn't trigger", () => {
  const s = { ...base, expectedArrivalAt: base.expectedArrivalAt + 5 * MIN };
  assert.equal(decideRecheck(s), null);
});

test("drift without a measured pace doesn't trigger", () => {
  assert.equal(decideRecheck({ ...base, paceMps: null, expectedArrivalAt: base.now }), null);
});

test("a plan made well before Go is rechecked right away", () => {
  assert.equal(decideRecheck({ ...base, stalePlan: true }), "stale");
});

test("never rechecks within 2 minutes of the last check", () => {
  const s = { ...base, lastCheckAt: base.now - RECHECK.minGapMs + 1, stalePlan: true, walkedSinceCheckM: 1000 };
  assert.equal(decideRecheck(s), null);
});

for (const [name, override] of [
  ["while already re-planning", { busy: true }],
  ["with the sun down", { sunUp: false }],
  ["while standing still", { paused: true }],
  ["close to a turn", { toNextTurnM: RECHECK.nearTurnM - 1 }],
  ["with under 10 minutes left", { remainingM: 1.3 * 9 * 60 }],
]) {
  test(`no recheck ${name}`, () => {
    assert.equal(decideRecheck({ ...base, ...override, stalePlan: true, lastCheckAt: 0 }), null);
  });
}

test("remaining time uses the default pace before one is measured", () => {
  // 700m at 1.3 m/s is ~9 minutes: too little left.
  assert.equal(decideRecheck({ ...base, paceMps: null, remainingM: 700, lastCheckAt: 0 }), null);
  assert.equal(decideRecheck({ ...base, paceMps: null, remainingM: 900, lastCheckAt: 0 }), "interval");
});

// --- is the new route better? --------------------------------------------

test("preferred fraction is weighted by distance", () => {
  const coords = [at(0, 0), at(0, 100), at(0, 400)];
  const segs = [{ shaded: true }, { shaded: false }, { shaded: false }];
  assert.ok(near(preferredFraction(coords, segs, "shade"), 0.25, 1e-9));
  assert.ok(near(preferredFraction(coords, segs, "sun"), 0.75, 1e-9));
});

test("preferred fraction of an empty or zero-length route is 0", () => {
  assert.equal(preferredFraction([at(0, 0)], [{ shaded: true }], "shade"), 0);
  assert.equal(preferredFraction([at(0, 0), at(0, 0)], [{ shaded: true }], "shade"), 0);
  assert.equal(preferredFraction(null, null, "shade"), 0);
});

test("switch only when clearly better", () => {
  assert.equal(isClearlyBetter(0.6, 0.5), false);
  assert.equal(isClearlyBetter(0.66, 0.5), true);
  assert.equal(isClearlyBetter(0.4, 0.5), false);
});
