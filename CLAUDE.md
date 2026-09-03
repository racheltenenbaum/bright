# Claude Code Instructions

## Testing (TDD)

Follow strict test-driven development for all backend feature work:

1. **Write failing tests first** — before writing any implementation code, write pytest tests in `tests/` that define the expected behavior. Run them and confirm they fail.
2. **Implement until tests pass** — write the minimum implementation needed to make the tests pass.
3. **Verify** — run `pytest tests/ --cov=src --cov-report=term-missing` and confirm all tests pass and coverage stays ≥99%.

Never report a feature complete without running pytest and confirming green. Tests must follow the patterns in `tests/conftest.py` (SQLite test DB, `clean_tables` autouse fixture, mocking via `unittest.mock`).

Coverage is enforced automatically in CI (`.github/workflows/tests.yml`, `--cov-fail-under=99`) — don't rely on the terminal's rounded percentage (e.g. "99%" can actually be 98.97%); check the precise number if it's close to the line.

## Shared thresholds/caps across modes or preferences

If a change adds a threshold, cap, or limit that applies across multiple modes/preferences/options that aren't symmetric in practice (e.g. a detour cap applied to both "sun" and "shade" routing, when shade structurally needs a bigger detour than sun to matter at all), write a test for **each** option that exercises the real end-to-end code path — not just a mocked unit test of the scoring function in isolation. A bug shipped for 3 months once because every shade-related test mocked path selection directly, so 99% line coverage never caught that shade silently collapsed to the same route as sun. See `test_optimized_route_sun_and_shade_produce_different_routes` in `tests/test_routing.py` for the pattern: build a real small graph, run the actual endpoint, and assert the two options produce genuinely different results.
