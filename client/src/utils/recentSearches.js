// Recent address searches for the route fields' dropdown. Per device and per
// account (keyed by user id, so a shared phone doesn't mix two people's
// history) — a convenience list, not data we need server-side.
const MAX_STORED = 8;

function storageKey(userId) {
  return `bright_recent_searches_${userId ?? "anon"}`;
}

export function loadRecentSearches(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return [];
  }
}

function store(userId, list) {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(list));
  } catch (_) {
    // Storage unavailable (private mode etc.) — recents just won't persist.
  }
  return list;
}

// Same place picked again moves to the top instead of duplicating.
function samePlace(a, b) {
  return Math.abs(a.lat - b.lat) < 1e-5 && Math.abs(a.lng - b.lng) < 1e-5;
}

export function addRecentSearch(userId, entry) {
  const list = loadRecentSearches(userId).filter((r) => !samePlace(r, entry));
  return store(userId, [{ ...entry, ts: Date.now() }, ...list].slice(0, MAX_STORED));
}

export function removeRecentSearch(userId, entry) {
  return store(userId, loadRecentSearches(userId).filter((r) => !samePlace(r, entry)));
}

export function clearRecentSearches(userId) {
  return store(userId, []);
}
