from unittest.mock import patch, MagicMock

ROUTE = [[51.5, -0.1], [51.502, -0.1], [51.504, -0.1]]
DATETIME = "2025-06-01T12:00:00"


def _mock_weather_ok():
    m = MagicMock()
    m.ok = True
    m.json.return_value = {"temperature": {"degrees": 18.0}, "uvIndex": 3, "cloudCover": 40}
    return m


# ── login rate limit ───────────────────────────────────────────────────────────

def test_login_rate_limit(client, test_user):
    creds = {"email": "test@example.com", "password": "password123"}
    for _ in range(3):
        r = client.post("/users/login", json=creds)
        assert r.status_code == 200
    response = client.post("/users/login", json=creds)
    assert response.status_code == 429


# ── weather rate limit ─────────────────────────────────────────────────────────

def test_weather_rate_limit(client, auth_headers):
    with patch("src.routers.weather.requests.get", return_value=_mock_weather_ok()), \
         patch("src.routers.weather.get_sun_position", return_value=(45.0, 180.0)):
        for _ in range(3):
            r = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)
            assert r.status_code == 200
        response = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)
    assert response.status_code == 429


# ── shadow-analyze rate limit ──────────────────────────────────────────────────

def test_shadow_analyze_rate_limit(client, auth_headers):
    with patch("src.routers.shadow_analyze.get_sun_position", return_value=(45.0, 180.0)):
        with patch("src.routers.shadow_analyze._fetch_buildings_for_bbox", return_value=[]):
            with patch("src.routers.shadow_analyze._fetch_elevations", return_value=[0.0] * len(ROUTE)):
                for _ in range(3):
                    r = client.post("/sun/shadow-analyze", json={
                        "coordinates": ROUTE, "datetime": DATETIME
                    }, headers=auth_headers)
                    assert r.status_code == 200
                response = client.post("/sun/shadow-analyze", json={
                    "coordinates": ROUTE, "datetime": DATETIME
                }, headers=auth_headers)
    assert response.status_code == 429


# ── coordinate validation ──────────────────────────────────────────────────────

def test_weather_invalid_lat(client, auth_headers):
    response = client.post("/weather/current", json={"lat": 999.0, "lng": -0.1}, headers=auth_headers)
    assert response.status_code == 422


def test_weather_invalid_lng(client, auth_headers):
    response = client.post("/weather/current", json={"lat": 51.5, "lng": 999.0}, headers=auth_headers)
    assert response.status_code == 422
