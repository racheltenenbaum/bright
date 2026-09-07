export function isCovered(lat, lng, regions) {
  return regions.some(
    ({ bounds }) =>
      lat >= bounds.south &&
      lat <= bounds.north &&
      lng >= bounds.west &&
      lng <= bounds.east,
  );
}
