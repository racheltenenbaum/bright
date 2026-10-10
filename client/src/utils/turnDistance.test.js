import { test } from "node:test";
import assert from "node:assert/strict";
import { roundTurnDistance } from "./turnDistance.js";

test("above 10m rounds to the nearest 10", () => {
  assert.equal(roundTurnDistance(47), 50);
  assert.equal(roundTurnDistance(44.9), 40);
  assert.equal(roundTurnDistance(12), 10);
  assert.equal(roundTurnDistance(15), 20);
  assert.equal(roundTurnDistance(183), 180);
});

test("between 5m and 10m rounds to the nearest 5", () => {
  assert.equal(roundTurnDistance(10), 10);
  assert.equal(roundTurnDistance(9), 10);
  assert.equal(roundTurnDistance(7.4), 5);
  assert.equal(roundTurnDistance(7.5), 10);
  assert.equal(roundTurnDistance(5.2), 5);
});

test("5m and below keeps single meters", () => {
  assert.equal(roundTurnDistance(5), 5);
  assert.equal(roundTurnDistance(4.4), 4);
  assert.equal(roundTurnDistance(3), 3);
  assert.equal(roundTurnDistance(1.2), 1);
});
