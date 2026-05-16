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
