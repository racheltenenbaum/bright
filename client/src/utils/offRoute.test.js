import { test } from "node:test";
import assert from "node:assert/strict";
import { OFF_ROUTE, createOffRouteDetector, distanceToRouteM } from "./offRoute.js";

// Local meters → [lat, lng] around (48.2, 16.37). x = east, y = north.
const M_LAT = 1 / 111_320;
const M_LNG = 1 / (111_320 * Math.cos((48.2 * Math.PI) / 180));
const at = (x, y) => [48.2 + y * M_LAT, 16.37 + x * M_LNG];

// A straight route 1km north, then 500m east.
const ROUTE = [at(0, 0), at(0, 1000), at(500, 1000)];

function fix(x, y, t, accuracy = 8) {
  const [lat, lng] = at(x, y);
  return { lat, lng, accuracy, time: t * 1000 };
}

// Feed fixes; returns the index of the first one that confirmed off-route, or -1.
function run(detector, fixes, route = ROUTE) {
  return fixes.findIndex((f) => detector.update(f, route));
}

test("distance is measured to the route line, not just its vertices", () => {
  assert.ok(Math.abs(distanceToRouteM(...at(40, 500), ROUTE) - 40) < 0.5);
  assert.ok(distanceToRouteM(...at(0, 500), ROUTE) < 0.5);
  assert.ok(Math.abs(distanceToRouteM(...at(250, 1030), ROUTE) - 30) < 0.5);
});

test("distance handles degenerate routes", () => {
  assert.equal(distanceToRouteM(...at(0, 0), []), Infinity);
  assert.ok(Math.abs(distanceToRouteM(...at(30, 0), [at(0, 0)]) - 30) < 0.5);
  assert.ok(Math.abs(distanceToRouteM(...at(30, 0), [at(0, 0), at(0, 0)]) - 30) < 0.5);
});

test("walking away from the route for a sustained stretch confirms off-route", () => {
  const d = createOffRouteDetector();
  // Turned off at y=300 and walked east, ~1.3 m/s, one fix every 5s.
  const fixes = [];
  for (let i = 0; i <= 20; i++) fixes.push(fix(10 + i * 6.5, 300, i * 5));
  const idx = run(d, fixes);
  assert.ok(idx > 0, "should confirm");
  const confirmed = fixes[idx];
  // Not before being well clear of the route for long enough.
  assert.ok(distanceToRouteM(confirmed.lat, confirmed.lng, ROUTE) - confirmed.accuracy > OFF_ROUTE.thresholdM);
});

test("each confirmation needs a full fresh window of evidence", () => {
  const d = createOffRouteDetector();
  const fixes = [];
  for (let i = 0; i <= 40; i++) fixes.push(fix(60 + i * 6.5, 300, i * 5));
  const hits = fixes.map((f, i) => (d.update(f, ROUTE) ? i : -1)).filter((i) => i >= 0);
  assert.ok(hits.length >= 1);
  for (let k = 1; k < hits.length; k++) {
    assert.ok(hits[k] - hits[k - 1] >= OFF_ROUTE.minFixes);
    assert.ok(fixes[hits[k]].time - fixes[hits[k - 1] + 1].time >= OFF_ROUTE.minDurationMs);
  }
});

test("walking on the route never confirms", () => {
  const d = createOffRouteDetector();
  const fixes = [];
  for (let i = 0; i < 150; i++) fixes.push(fix(0, i * 6.5, i * 5));  // up to the corner at 1000m
  assert.equal(run(d, fixes), -1);
});

test("opposite sidewalk of a wide street never confirms", () => {
  const d = createOffRouteDetector();
  const fixes = [];
  for (let i = 0; i < 100; i++) fixes.push(fix(25, i * 6.5, i * 5));
  assert.equal(run(d, fixes), -1);
});

test("poor-accuracy fixes never count, however far they appear", () => {
  const d = createOffRouteDetector();
  const fixes = [];
  for (let i = 0; i < 100; i++) fixes.push(fix(200, i * 6.5, i * 5, OFF_ROUTE.maxAccuracyM + 1));
  assert.equal(run(d, fixes), -1);
});

test("fixes with no accuracy are treated as unreliable", () => {
  const d = createOffRouteDetector();
  const fixes = [];
  for (let i = 0; i < 100; i++) fixes.push({ ...fix(200, i * 6.5, i * 5), accuracy: undefined });
  assert.equal(run(d, fixes), -1);
});

test("a fix whose error circle still reaches the route doesn't count", () => {
  // 50m away but ±30m: could really be 20m away, i.e. on the route.
  const d = createOffRouteDetector();
  const fixes = [];
  for (let i = 0; i < 100; i++) fixes.push(fix(50, i * 6.5, i * 5, 30));
  assert.equal(run(d, fixes), -1);
});

test("GPS drift while standing still never confirms", () => {
  // Standing in a café 60m off the route: fixes jitter a few meters but
  // the walker isn't going anywhere yet.
  const d = createOffRouteDetector();
  const fixes = [];
  for (let i = 0; i < 100; i++) fixes.push(fix(60 + (i % 3) * 2, 300 + (i % 2) * 3, i * 5));
  assert.equal(run(d, fixes), -1);
});

test("a brief excursion that returns to the route doesn't confirm", () => {
  const d = createOffRouteDetector();
  const fixes = [
    fix(0, 100, 0),
    fix(50, 110, 5), fix(55, 120, 10),     // ducked off briefly
    fix(5, 130, 15),                        // back on the route — streak resets
    fix(50, 140, 20), fix(55, 150, 25),    // off again, but not long enough
    fix(0, 160, 30),
  ];
  assert.equal(run(d, fixes), -1);
});

test("a single wild fix inside a run of on-route fixes doesn't confirm", () => {
  const d = createOffRouteDetector();
  const fixes = [];
  for (let i = 0; i < 60; i++) fixes.push(i % 10 === 5 ? fix(300, i * 6.5, i * 5) : fix(0, i * 6.5, i * 5));
  assert.equal(run(d, fixes), -1);
});

test("needs both enough fixes and enough time", () => {
  // Plenty of fixes, all within a couple of seconds: not enough time.
  const d1 = createOffRouteDetector();
  const burst = [];
  for (let i = 0; i < 20; i++) burst.push(fix(60 + i * 2, 300, i * 0.1));
  assert.equal(run(d1, burst), -1);

  // Plenty of time but too few fixes (e.g. a stalled GPS feed).
  const d2 = createOffRouteDetector();
  assert.equal(run(d2, [fix(60, 300, 0), fix(100, 300, 60)]), -1);
});

test("ambiguous fixes neither count nor reset the streak", () => {
  const d = createOffRouteDetector();
  const fixes = [
    fix(60, 300, 0), fix(70, 300, 5),
    fix(45, 300, 8, 30),                    // ambiguous: 45m ±30m
    fix(80, 300, 10), fix(90, 300, 15), fix(100, 300, 20),
  ];
  // Confirms at 90 (4 counted fixes over 15s): the ambiguous fix neither
  // added to the streak nor restarted it.
  assert.equal(run(d, fixes), 4);
});

test("reset clears an in-progress streak", () => {
  const d = createOffRouteDetector();
  run(d, [fix(60, 300, 0), fix(70, 300, 5), fix(80, 300, 10)]);
  d.reset();
  assert.equal(run(d, [fix(90, 300, 15)]), -1);
});

test("no usable route never confirms", () => {
  const d = createOffRouteDetector();
  const fixes = [];
  for (let i = 0; i < 20; i++) fixes.push(fix(200, 300, i * 5));
  assert.equal(run(d, fixes, null), -1);
  assert.equal(run(d, fixes, [at(0, 0)]), -1);
});
