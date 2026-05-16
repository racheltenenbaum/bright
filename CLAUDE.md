# Claude Code Instructions

## Testing (TDD)

Follow strict test-driven development for all backend feature work:

1. **Write failing tests first** — before writing any implementation code, write pytest tests in `tests/` that define the expected behavior. Run them and confirm they fail.
2. **Implement until tests pass** — write the minimum implementation needed to make the tests pass.
3. **Verify** — run `pytest tests/ --cov=src --cov-report=term-missing` and confirm all tests pass and coverage stays ≥99%.

Never report a feature complete without running pytest and confirming green. Tests must follow the patterns in `tests/conftest.py` (SQLite test DB, `clean_tables` autouse fixture, mocking via `unittest.mock`).
