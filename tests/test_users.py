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
