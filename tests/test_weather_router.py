from unittest.mock import patch, MagicMock
import src.routers.weather as weather_module


def _mock_ok(body):
    m = MagicMock()
    m.ok = True
    m.json.return_value = body
    return m


def _mock_fail():
    m = MagicMock()
    m.ok = False
    return m


WEATHER_BODY = {
    "temperature": {"degrees": 18.5},
    "uvIndex": 3,
    "cloudCover": 40,
    "weatherCondition": {
        "iconBaseUri": "https://example.com/sunny",
        "description": {"text": "Sunny"},
    },
}

SUN_UP = (45.0, 180.0)
SUN_DOWN = (-5.0, 180.0)


def test_weather_success(client, auth_headers):
    with patch("src.routers.weather.requests.get", return_value=_mock_ok(WEATHER_BODY)), \
         patch("src.routers.weather.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.weather._get_local_datetime", return_value=("2025-06-01", "12:00:00")):
        response = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["temperature"] == 18.5
    assert data["uv_index"] == 3
    assert data["cloud_cover"] == 40
    assert data["icon_url"] == "https://example.com/sunny.png"
    assert data["condition"] == "Sunny"
    assert data["sun_altitude"] == 45.0


def test_weather_no_condition_field(client, auth_headers):
    body = {"temperature": {"degrees": 10.0}, "uvIndex": 1, "cloudCover": 80}
    with patch("src.routers.weather.requests.get", return_value=_mock_ok(body)), \
         patch("src.routers.weather.get_sun_position", return_value=SUN_DOWN), \
         patch("src.routers.weather._get_local_datetime", return_value=("2025-06-01", "22:00:00")):
        response = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["icon_url"] is None
    assert data["condition"] is None
    assert data["sun_altitude"] == -5.0


def test_weather_api_error(client, auth_headers):
    with patch("src.routers.weather.requests.get", return_value=_mock_fail()), \
         patch("src.routers.weather.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.weather._get_local_datetime", return_value=("2025-06-01", "12:00:00")):
        response = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)
    assert response.status_code == 502


def test_weather_unauthenticated(client):
    response = client.post("/weather/current", json={"lat": 51.5, "lng": -0.1})
    assert response.status_code == 401


def test_get_local_datetime_uses_timezone_api():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"timeZoneId": "America/New_York"}
    with patch("src.routers.weather.GOOGLE_API_KEY", "fake-key"), \
         patch("src.routers.weather.requests.get", return_value=mock_resp):
        date_str, time_str = weather_module._get_local_datetime(40.7, -74.0)
    assert len(date_str) == 10
    assert len(time_str) == 8


def test_get_local_datetime_falls_back_to_utc_on_error():
    with patch("src.routers.weather.GOOGLE_API_KEY", "fake-key"), \
         patch("src.routers.weather.requests.get", side_effect=Exception("network")):
        date_str, time_str = weather_module._get_local_datetime(51.5, -0.1)
    assert len(date_str) == 10
    assert len(time_str) == 8


def test_get_local_datetime_no_api_key():
    with patch("src.routers.weather.GOOGLE_API_KEY", None):
        date_str, time_str = weather_module._get_local_datetime(51.5, -0.1)
    assert len(date_str) == 10
    assert len(time_str) == 8
