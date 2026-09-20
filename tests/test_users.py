from unittest.mock import patch


def test_register_success(client):
    response = client.post("/users/register", json={
        "first_name": "Alice", "email": "alice@example.com", "password": "secret123"
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["first_name"] == "Alice"


def test_register_duplicate_email(client, test_user):
    response = client.post("/users/register", json={
        "first_name": "Copy", "email": "test@example.com", "password": "secret123"
    })
    assert response.status_code == 400


def test_login_success(client, test_user):
    response = client.post("/users/login", json={
        "email": "test@example.com", "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@example.com"


def test_login_wrong_password(client, test_user):
    response = client.post("/users/login", json={
        "email": "test@example.com", "password": "wrongpassword"
    })
    assert response.status_code == 401


def test_login_unknown_email(client):
    response = client.post("/users/login", json={
        "email": "ghost@example.com", "password": "password123"
    })
    assert response.status_code == 401


def test_update_name_success(client, auth_headers):
    response = client.patch("/users/me", json={"first_name": "Rachel"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["first_name"] == "Rachel"


def test_update_name_blank_rejected(client, auth_headers):
    response = client.patch("/users/me", json={"first_name": "  "}, headers=auth_headers)
    assert response.status_code == 422


def test_update_name_explicit_null_allowed(client, auth_headers):
    """first_name: null means 'leave unchanged', distinct from a blank string."""
    response = client.patch("/users/me", json={"first_name": None}, headers=auth_headers)
    assert response.status_code == 200


def test_update_name_unauthenticated(client):
    response = client.patch("/users/me", json={"first_name": "Rachel"})
    assert response.status_code == 401


def test_register_default_pref_max_detour(client):
    response = client.post("/users/register", json={
        "first_name": "Alice", "email": "alice@example.com", "password": "secret123"
    })
    assert response.status_code == 201
    assert response.json()["user"]["pref_max_detour"] == 30


def test_update_pref_max_detour(client, auth_headers):
    response = client.patch("/users/me", json={"pref_max_detour": 50}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["pref_max_detour"] == 50


def test_update_name_and_pref_max_detour(client, auth_headers):
    response = client.patch("/users/me", json={"first_name": "Rachel", "pref_max_detour": 70}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["first_name"] == "Rachel"
    assert response.json()["pref_max_detour"] == 70


def test_update_pref_max_detour_out_of_range(client, auth_headers):
    response = client.patch("/users/me", json={"pref_max_detour": 150}, headers=auth_headers)
    assert response.status_code == 422


def test_register_default_pref_mode(client):
    response = client.post("/users/register", json={
        "first_name": "Alice", "email": "alice@example.com", "password": "secret123"
    })
    assert response.status_code == 201
    assert response.json()["user"]["pref_mode"] == "sun"


def test_update_pref_mode_shade(client, auth_headers):
    response = client.patch("/users/me", json={"pref_mode": "shade"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["pref_mode"] == "shade"


def test_update_pref_mode_invalid(client, auth_headers):
    response = client.patch("/users/me", json={"pref_mode": "cloudy"}, headers=auth_headers)
    assert response.status_code == 422


def test_register_default_pref_map_controls(client):
    response = client.post("/users/register", json={
        "first_name": "Alice", "email": "alice@example.com", "password": "secret123"
    })
    assert response.status_code == 201
    assert response.json()["user"]["pref_map_controls"] is False


def test_update_pref_map_controls_enabled(client, auth_headers):
    response = client.patch("/users/me", json={"pref_map_controls": True}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["pref_map_controls"] is True


def test_update_pref_map_controls_disabled(client, auth_headers):
    response = client.patch("/users/me", json={"pref_map_controls": True}, headers=auth_headers)
    assert response.status_code == 200
    response = client.patch("/users/me", json={"pref_map_controls": False}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["pref_map_controls"] is False


def test_register_default_pref_map_type(client):
    response = client.post("/users/register", json={
        "first_name": "Alice", "email": "alice@example.com", "password": "secret123"
    })
    assert response.status_code == 201
    assert response.json()["user"]["pref_map_type"] == "roadmap"


def test_update_pref_map_type_satellite(client, auth_headers):
    response = client.patch("/users/me", json={"pref_map_type": "satellite"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["pref_map_type"] == "satellite"


def test_update_pref_map_type_terrain(client, auth_headers):
    response = client.patch("/users/me", json={"pref_map_type": "terrain"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["pref_map_type"] == "terrain"


def test_update_pref_map_type_invalid(client, auth_headers):
    response = client.patch("/users/me", json={"pref_map_type": "moonmap"}, headers=auth_headers)
    assert response.status_code == 422


def test_register_password_too_short(client):
    response = client.post("/users/register", json={
        "first_name": "Alice", "email": "alice@example.com", "password": "abc"
    })
    assert response.status_code == 422


def test_register_password_no_number(client):
    response = client.post("/users/register", json={
        "first_name": "Alice", "email": "alice@example.com", "password": "abcdefgh"
    })
    assert response.status_code == 422


def test_delete_account_success(client, auth_headers):
    response = client.delete("/users/me", headers=auth_headers)
    assert response.status_code == 204


def test_delete_account_unauthenticated(client):
    response = client.delete("/users/me")
    assert response.status_code == 401


def test_delete_account_removes_login(client, auth_headers):
    client.delete("/users/me", headers=auth_headers)
    response = client.post("/users/login", json={
        "email": "test@example.com", "password": "password123"
    })
    assert response.status_code == 401


def test_delete_account_cascades_routes_and_spots(client, auth_headers, db, test_user):
    from src.models import Route, Spot

    user_id = test_user.id
    db.add(Route(
        name="Commute", start_lat=1, start_lng=1, end_lat=2, end_lng=2,
        user_id=user_id,
    ))
    db.add(Spot(
        name="Bench", address="1 Main St", lat=1, lng=1, icon="faStar",
        user_id=user_id,
    ))
    db.commit()

    response = client.delete("/users/me", headers=auth_headers)
    assert response.status_code == 204

    assert db.query(Route).filter(Route.user_id == user_id).count() == 0
    assert db.query(Spot).filter(Spot.user_id == user_id).count() == 0


def test_register_rate_limited(client):
    for i in range(3):
        client.post("/users/register", json={
            "first_name": f"User{i}", "email": f"user{i}@example.com", "password": "secret123"
        })
    response = client.post("/users/register", json={
        "first_name": "Extra", "email": "extra@example.com", "password": "secret123"
    })
    assert response.status_code == 429


# --- Google / Apple sign-in ---

def test_google_auth_creates_new_user(client, db):
    from src.models import User

    idinfo = {"sub": "g-1", "email": "newgoogle@example.com", "given_name": "Gia", "email_verified": True}
    with patch("src.routers.users.verify_google_token", return_value=idinfo):
        response = client.post("/users/auth/google", json={"id_token": "fake"})
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "newgoogle@example.com"
    assert data["user"]["first_name"] == "Gia"
    assert "access_token" in data

    user = db.query(User).filter(User.email == "newgoogle@example.com").first()
    assert user.google_sub == "g-1"
    assert user.hashed_password is None


def test_google_auth_falls_back_to_placeholder_name(client):
    idinfo = {"sub": "g-2", "email": "noname@example.com", "email_verified": True}
    with patch("src.routers.users.verify_google_token", return_value=idinfo):
        response = client.post("/users/auth/google", json={"id_token": "fake"})
    assert response.status_code == 200
    assert response.json()["user"]["first_name"] == "there"


def test_google_auth_existing_google_sub_logs_in_same_user(client):
    idinfo = {"sub": "g-3", "email": "repeat@example.com", "given_name": "Rae", "email_verified": True}
    with patch("src.routers.users.verify_google_token", return_value=idinfo):
        first = client.post("/users/auth/google", json={"id_token": "fake"})
        second = client.post("/users/auth/google", json={"id_token": "fake"})
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


def test_google_auth_links_existing_password_account_by_email(client, test_user):
    idinfo = {"sub": "g-4", "email": "test@example.com", "given_name": "Test", "email_verified": True}
    with patch("src.routers.users.verify_google_token", return_value=idinfo):
        response = client.post("/users/auth/google", json={"id_token": "fake"})
    assert response.status_code == 200
    assert response.json()["user"]["id"] == test_user.id

    # Password login still works after linking — the existing password wasn't touched.
    login_response = client.post("/users/login", json={"email": "test@example.com", "password": "password123"})
    assert login_response.status_code == 200


def test_google_auth_linking_does_not_overwrite_existing_name(client, test_user):
    # test_user's first_name is "Test" — Google reporting a different name
    # (as it would for someone who registered manually, then also signed in
    # with Google under the same email) must not clobber it.
    idinfo = {"sub": "g-6", "email": "test@example.com", "given_name": "Googley", "email_verified": True}
    with patch("src.routers.users.verify_google_token", return_value=idinfo):
        response = client.post("/users/auth/google", json={"id_token": "fake"})
    assert response.status_code == 200
    assert response.json()["user"]["first_name"] == "Test"


def test_apple_auth_creates_new_user_with_provided_name(client, db):
    from src.models import User

    claims = {"sub": "a-1", "email": "newapple@example.com"}
    with patch("src.routers.users.verify_apple_token", return_value=claims):
        response = client.post("/users/auth/apple", json={"id_token": "fake", "first_name": "Ann"})
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "newapple@example.com"
    assert data["user"]["first_name"] == "Ann"

    user = db.query(User).filter(User.email == "newapple@example.com").first()
    assert user.apple_sub == "a-1"
    assert user.hashed_password is None


def test_apple_auth_without_name_falls_back_to_placeholder_name(client):
    claims = {"sub": "a-2", "email": "noname@example.com"}
    with patch("src.routers.users.verify_apple_token", return_value=claims):
        response = client.post("/users/auth/apple", json={"id_token": "fake"})
    assert response.status_code == 200
    assert response.json()["user"]["first_name"] == "there"


def test_apple_auth_missing_email_rejected(client):
    claims = {"sub": "a-3"}
    with patch("src.routers.users.verify_apple_token", return_value=claims):
        response = client.post("/users/auth/apple", json={"id_token": "fake"})
    assert response.status_code == 400


def test_apple_auth_links_existing_password_account_by_email(client, test_user):
    claims = {"sub": "a-4", "email": "test@example.com"}
    with patch("src.routers.users.verify_apple_token", return_value=claims):
        response = client.post("/users/auth/apple", json={"id_token": "fake"})
    assert response.status_code == 200
    assert response.json()["user"]["id"] == test_user.id


def test_apple_auth_linking_does_not_overwrite_existing_name(client, test_user):
    claims = {"sub": "a-5", "email": "test@example.com"}
    with patch("src.routers.users.verify_apple_token", return_value=claims):
        response = client.post("/users/auth/apple", json={"id_token": "fake", "first_name": "Appley"})
    assert response.status_code == 200
    assert response.json()["user"]["first_name"] == "Test"


def test_oauth_only_account_cannot_password_login(client):
    idinfo = {"sub": "g-5", "email": "oauthonly@example.com", "given_name": "Only", "email_verified": True}
    with patch("src.routers.users.verify_google_token", return_value=idinfo):
        client.post("/users/auth/google", json={"id_token": "fake"})

    response = client.post("/users/login", json={"email": "oauthonly@example.com", "password": "whatever123"})
    assert response.status_code == 401
