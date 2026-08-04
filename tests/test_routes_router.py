import pytest
from src.models import Route

ROUTE_PAYLOAD = {
    "name": "Morning Walk",
    "description": "Nice route",
    "start_lat": 51.5, "start_lng": -0.1,
    "end_lat": 51.51, "end_lng": -0.1,
    "start_address": "Start St",
    "end_address": "End St",
    "preference": "sun",
}


def test_create_route(client, auth_headers):
    response = client.post("/routes", json=ROUTE_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Morning Walk"
    assert data["start_lat"] == 51.5
    assert data["preference"] == "sun"


def test_create_route_shade_preference(client, auth_headers):
    payload = {**ROUTE_PAYLOAD, "preference": "shade"}
    response = client.post("/routes", json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["preference"] == "shade"


def test_create_route_no_preference(client, auth_headers):
    payload = {k: v for k, v in ROUTE_PAYLOAD.items() if k != "preference"}
    response = client.post("/routes", json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["preference"] is None


def test_create_route_unauthenticated(client):
    response = client.post("/routes", json=ROUTE_PAYLOAD)
    assert response.status_code == 401


def test_get_routes_empty(client, auth_headers):
    response = client.get("/routes", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_routes_returns_own_routes(client, auth_headers, test_user, db):
    route = Route(name="My Walk", user_id=test_user.id,
                  start_lat=51.5, start_lng=-0.1, end_lat=51.51, end_lng=-0.1)
    db.add(route)
    db.commit()

    response = client.get("/routes", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "My Walk"


def test_delete_route(client, auth_headers, test_user, db):
    route = Route(name="Delete Me", user_id=test_user.id,
                  start_lat=51.5, start_lng=-0.1, end_lat=51.51, end_lng=-0.1)
    db.add(route)
    db.commit()

    response = client.delete(f"/routes/{route.id}", headers=auth_headers)
    assert response.status_code == 204


def test_delete_nonexistent_route(client, auth_headers):
    response = client.delete("/routes/99999", headers=auth_headers)
    assert response.status_code == 204


def test_share_route_generates_token(client, auth_headers, test_user, db):
    route = Route(name="Share Me", user_id=test_user.id,
                  start_lat=51.5, start_lng=-0.1, end_lat=51.51, end_lng=-0.1)
    db.add(route)
    db.commit()

    response = client.post(f"/routes/{route.id}/share", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "share_token" in data
    assert len(data["share_token"]) > 0


def test_share_route_idempotent(client, auth_headers, test_user, db):
    route = Route(name="Share Me", user_id=test_user.id,
                  start_lat=51.5, start_lng=-0.1, end_lat=51.51, end_lng=-0.1)
    db.add(route)
    db.commit()

    r1 = client.post(f"/routes/{route.id}/share", headers=auth_headers)
    r2 = client.post(f"/routes/{route.id}/share", headers=auth_headers)
    assert r1.json()["share_token"] == r2.json()["share_token"]


def test_share_route_unauthenticated(client, test_user, db):
    route = Route(name="Share Me", user_id=test_user.id,
                  start_lat=51.5, start_lng=-0.1, end_lat=51.51, end_lng=-0.1)
    db.add(route)
    db.commit()

    response = client.post(f"/routes/{route.id}/share")
    assert response.status_code == 401


def test_share_route_wrong_user(client, db):
    from src.auth import create_access_token
    from src.models import User
    import bcrypt

    other = User(first_name="Other", email="other@example.com",
                 hashed_password=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode())
    db.add(other)
    db.commit()
    db.refresh(other)
    route = Route(name="Not Yours", user_id=other.id,
                  start_lat=51.5, start_lng=-0.1, end_lat=51.51, end_lng=-0.1)
    db.add(route)
    db.commit()

    headers = {"Authorization": f"Bearer {create_access_token(other.id + 999)}"}
    response = client.post(f"/routes/{route.id}/share", headers=headers)
    assert response.status_code in (401, 404)


def test_create_route_with_path(client, auth_headers):
    payload = {**ROUTE_PAYLOAD, "route_path": "[[51.5,-0.1],[51.505,-0.1],[51.51,-0.1]]"}
    response = client.post("/routes", json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["route_path"] == "[[51.5,-0.1],[51.505,-0.1],[51.51,-0.1]]"


def test_create_route_without_path(client, auth_headers):
    response = client.post("/routes", json=ROUTE_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["route_path"] is None


def test_get_shared_route_public(client, test_user, db):
    route = Route(name="Public Walk", user_id=test_user.id,
                  start_lat=51.5, start_lng=-0.1, end_lat=51.51, end_lng=-0.1,
                  share_token="test-token-abc",
                  route_path="[[51.5,-0.1],[51.51,-0.1]]")
    db.add(route)
    db.commit()

    response = client.get("/share/test-token-abc")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Public Walk"
    assert data["start_lat"] == 51.5
    assert data["route_path"] == "[[51.5,-0.1],[51.51,-0.1]]"


def test_get_shared_route_not_found(client):
    response = client.get("/share/nonexistent-token")
    assert response.status_code == 404


def test_create_route_invalid_preference_rejected(client, auth_headers):
    response = client.post("/routes", json={**ROUTE_PAYLOAD, "preference": "windy"}, headers=auth_headers)
    assert response.status_code == 422
