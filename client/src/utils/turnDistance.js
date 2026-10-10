// Spoken/displayed turn distances: precise numbers like "in 47m" sound odd
// and are false precision for GPS, so round to 10s above 10m and 5s above
// 5m; only the last few meters are said exactly.
export function roundTurnDistance(meters) {
  if (meters > 10) return Math.round(meters / 10) * 10;
  if (meters > 5) return Math.round(meters / 5) * 5;
  return Math.round(meters);
}
