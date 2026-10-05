# Claude Code Instructions

## Testing (TDD)

Follow strict test-driven development for all backend feature work:

1. **Write failing tests first** — before writing any implementation code, write pytest tests in `tests/` that define the expected behavior. Run them and confirm they fail.
2. **Implement until tests pass** — write the minimum implementation needed to make the tests pass.
3. **Verify** — run `pytest tests/ --cov=src --cov-report=term-missing` and confirm all tests pass and coverage stays ≥99%.

Never report a feature complete without running pytest and confirming green. Tests must follow the patterns in `tests/conftest.py` (SQLite test DB, `clean_tables` autouse fixture, mocking via `unittest.mock`).

Coverage is enforced automatically in CI (`.github/workflows/tests.yml`, `--cov-fail-under=99`) — don't rely on the terminal's rounded percentage (e.g. "99%" can actually be 98.97%); check the precise number if it's close to the line.

## Production database safety

Never delete anything from the production database on your own judgment — no `DROP TABLE`, `DELETE FROM`, `ALTER TABLE ... DROP COLUMN`, dropping/truncating data, or any other destructive operation against production data or schema, even if it looks safe, reversible, or clearly implied by the request. This must never happen autonomously.

Before running or proposing any destructive operation against the production DB, stop and ask Rachel for explicit confirmation — **three separate times** (three distinct asks, each requiring an explicit yes), not just once, before proceeding. This applies even to things that seem obviously fine, like dropping a column added by mistake, clearing a test/debug row, or an Alembic `downgrade()` that includes a `DROP COLUMN`/`DROP TABLE`.

Purely additive changes (`CREATE TABLE`, `ADD COLUMN`, etc.) are not covered by this rule and don't need the triple confirmation — only anything that removes or destroys existing data or schema does.

## Shared thresholds/caps across modes or preferences

If a change adds a threshold, cap, or limit that applies across multiple modes/preferences/options that aren't symmetric in practice (e.g. a detour cap applied to both "sun" and "shade" routing, when shade structurally needs a bigger detour than sun to matter at all), write a test for **each** option that exercises the real end-to-end code path — not just a mocked unit test of the scoring function in isolation. A bug shipped for 3 months once because every shade-related test mocked path selection directly, so 99% line coverage never caught that shade silently collapsed to the same route as sun. See `test_optimized_route_sun_and_shade_produce_different_routes` in `tests/test_routing.py` for the pattern: build a real small graph, run the actual endpoint, and assert the two options produce genuinely different results.

## Design & branding (bright's own rules — keep exactly as-is)

These are bright's design preferences as they stood on 2026-10-05, copied
here when Rachel's general design rules moved to the web dev portfolio.
They are bright's rules and must be kept for all bright UI, website and
email work. Rules from other projects (e.g. the portfolio's "no borders /
square corners") do not apply to bright.

### Design aesthetic

- Clean, feminine, soft, and modern. Generous whitespace, rounded corners.
- No shadowing, ever: no box-shadow, text-shadow, drop-shadow filters,
  blurred "fake shadow" layers, or soft radial glow blobs/cursor glows
  (they read as grey shadows). Separate surfaces with background color
  contrast or a subtle 1px border instead.
- Warm/soft color palettes (e.g. terracotta, blush, sage, cream) rather than
  stark or corporate ones — but confirm the specific palette per project
  rather than assuming.
- Pair a display serif (for headings) with a clean sans-serif (for body) —
  e.g. Fraunces/Cormorant Garamond + Poppins.
- Always include some interactive/delightful touches: scroll reveals, hover
  states, subtle motion — but nothing gimmicky or slow.
- Prefer real photography over generic gradient placeholders when it's
  feasible to source real, appropriately-licensed images (verify content and
  license before using — don't guess stock-photo URLs from memory).
- When a brand name, palette, or other identity-defining detail isn't
  decided yet, use an obvious placeholder (e.g. "Studio Name") rather than
  inventing a specific brand — make it easy to find-and-replace later.
- Never add "You are viewing a sample project…" (or similar) banners/headers
  to a page. Demo/portfolio framing like this reads as unpolished and
  breaks the illusion that it's a real site.
- Scroll-triggered reveal animations (fade-in/slide-in on scroll) should be
  fast — content the user scrolls to should already be visible almost
  immediately, not lag behind the scroll. Keep reveal transition durations
  short (roughly 0.2–0.3s); don't let users scroll faster than content can
  appear.
- Don't add a "Back to [Studio/agency name]" link in page footers.

### Logos & branding (hard rules)

- A logo Rachel provides is the source of truth for that brand's palette.
  Extract the actual colors from the logo file and use those as the site's
  core colors — do not invent, substitute, or "interpret" a different
  palette that was merely inspired by the logo.
- Never guess or reinterpret a logo. If a logo is ambiguous, low-res, or you
  need a different version/variant (different crop, icon-only, no
  background, etc.), ask Rachel for it — she will provide it. Don't work
  around a bad asset by approximating it in code.
- If the logo file has a non-white/non-transparent background, every place
  it's placed must either (a) sit on a container with that exact same
  background color (e.g. the navbar matches the logo's background), or
  (b) have that background removed so the logo drops in transparently. It
  must never look pasted in a mismatched box — it has to be seamless with
  whatever surface it's on.
- Don't guess a font family to "match" a logo's lettering. If the site needs
  a font compatible with the logo's type, ask Rachel for it — she will
  provide it.
- Avoid pill-shaped buttons/CTAs as a default — they read as generic and
  copy-paste. Vary button shape/treatment per brand instead of reaching for
  the same rounded pill everywhere.
