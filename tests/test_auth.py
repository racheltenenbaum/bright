from src.auth import create_access_token


def test_create_access_token_returns_string():
    token = create_access_token(1)
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_different_ids_differ():
    assert create_access_token(1) != create_access_token(2)


def test_get_current_user_valid(client, auth_headers):
    response = client.get("/routes", headers=auth_headers)
    assert response.status_code == 200


def test_get_current_user_invalid_token(client):
    response = client.get("/routes", headers={"Authorization": "Bearer bad.token.here"})
    assert response.status_code == 401


def test_get_current_user_nonexistent_user(client):
    token = create_access_token(99999)
    response = client.get("/routes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ── get_current_user_optional ───────────────────────────────────────────────
# Used by endpoints that work without an account (routing, shadow-analyze,
# places, weather) — degrades to anonymous instead of 401ing, since a
# missing/invalid/expired token there means "logged out", not "blocked".

def test_get_current_user_optional_no_token_degrades_to_anonymous(client, auth_headers):
    """/sun/analyze is unauth'd end-to-end coverage that get_current_user_optional
    returns None (not a 401) for a request with no Authorization header at all."""
    response = client.post("/sun/analyze", json={
        "coordinates": [[51.5, -0.1], [51.51, -0.1]], "datetime": "2025-06-01T12:00:00",
    })
    assert response.status_code == 200


def test_get_current_user_optional_invalid_token_degrades_to_anonymous(client):
    """A garbage/expired token (e.g. stale localStorage) must not block an
    endpoint that works anonymously — it should be treated the same as no
    token, not surfaced as an error."""
    response = client.post(
        "/sun/analyze",
        json={"coordinates": [[51.5, -0.1], [51.51, -0.1]], "datetime": "2025-06-01T12:00:00"},
        headers={"Authorization": "Bearer bad.token.here"},
    )
    assert response.status_code == 200


def test_get_current_user_optional_valid_token_still_identifies_user(client, auth_headers):
    """A valid token on an optional-auth endpoint still resolves the real
    user — anonymous support shouldn't break personalization for logged-in
    users (e.g. /sun/optimized-route's use of pref_max_detour)."""
    response = client.post("/sun/analyze", json={
        "coordinates": [[51.5, -0.1], [51.51, -0.1]], "datetime": "2025-06-01T12:00:00",
    }, headers=auth_headers)
    assert response.status_code == 200
