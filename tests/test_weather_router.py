from unittest.mock import patch, MagicMock


def _mock_ok(body):
    m = MagicMock()
    m.ok = True
    m.json.return_value = body
    return m


def _mock_fail():
    m = MagicMock()
    m.ok = False
    return m


def test_weather_success(client, auth_headers):
    body = {
        "temperature": {"degrees": 18.5},
        "uvIndex": 3,
        "cloudCover": 40,
        "weatherCondition": {
            "iconBaseUri": "https://example.com/sunny",
            "description": {"text": "Sunny"},
        },
    }
    with patch("requests.get", return_value=_mock_ok(body)):
        response = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["temperature"] == 18.5
    assert data["uv_index"] == 3
    assert data["cloud_cover"] == 40
    assert data["icon_url"] == "https://example.com/sunny.png"
    assert data["condition"] == "Sunny"


def test_weather_no_condition_field(client, auth_headers):
    body = {"temperature": {"degrees": 10.0}, "uvIndex": 1, "cloudCover": 80}
    with patch("requests.get", return_value=_mock_ok(body)):
        response = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["icon_url"] is None
    assert data["condition"] is None


def test_weather_api_error(client, auth_headers):
    with patch("requests.get", return_value=_mock_fail()):
        response = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)
    assert response.status_code == 502


def test_weather_unauthenticated(client):
    response = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1})
    assert response.status_code == 401
