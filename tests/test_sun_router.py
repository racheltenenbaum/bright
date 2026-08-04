from unittest.mock import patch

COORDS = [[51.5, -0.1], [51.51, -0.1]]
DATETIME = "2025-06-01T12:00:00"


def test_sun_analyze_success(client, auth_headers):
    with patch("src.routers.sun.get_sun_position", return_value=(45.0, 180.0)):
        response = client.post("/sun/analyze", json={
            "coordinates": COORDS, "datetime": DATETIME
        }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sun_altitude"] == 45.0
    assert data["sun_azimuth"] == 180.0
    assert "date" in data


def test_sun_analyze_too_few_coords(client, auth_headers):
    response = client.post("/sun/analyze", json={
        "coordinates": [[51.5, -0.1]], "datetime": DATETIME
    }, headers=auth_headers)
    assert response.status_code == 400


def test_sun_analyze_unauthenticated(client):
    response = client.post("/sun/analyze", json={
        "coordinates": COORDS, "datetime": DATETIME
    })
    assert response.status_code == 401


def test_optimized_route_malformed_datetime(client, auth_headers):
    response = client.post("/sun/optimized-route", json={
        "start": [51.5, -0.1],
        "end": [51.51, -0.1],
        "datetime": "not-a-date",
        "preference": "sun",
    }, headers=auth_headers)
    assert response.status_code == 422


def test_optimized_route_invalid_preference(client, auth_headers):
    response = client.post("/sun/optimized-route", json={
        "start": [51.5, -0.1],
        "end": [51.51, -0.1],
        "datetime": DATETIME,
        "preference": "tornado",
    }, headers=auth_headers)
    assert response.status_code == 422
