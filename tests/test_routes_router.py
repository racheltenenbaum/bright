import pytest
from src.models import Route

ROUTE_PAYLOAD = {
    "name": "Morning Walk",
    "description": "Nice route",
    "start_lat": 51.5, "start_lng": -0.1,
    "end_lat": 51.51, "end_lng": -0.1,
    "start_address": "Start St",
    "end_address": "End St",
}


def test_create_route(client, auth_headers):
    response = client.post("/routes", json=ROUTE_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Morning Walk"
    assert data["start_lat"] == 51.5


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
