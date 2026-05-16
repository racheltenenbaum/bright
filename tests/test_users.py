def test_register_success(client):
    response = client.post("/users/register", json={
        "first_name": "Alice", "email": "alice@example.com", "password": "secret123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["first_name"] == "Alice"
    assert "id" in data


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
