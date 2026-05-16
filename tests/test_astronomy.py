import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from src.utils.astronomy import get_sun_position


def _mock_resp(status=200, body=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = body or {}
    return m


def test_get_sun_position_success_nested():
    resp = _mock_resp(200, {"astronomy": {"sun_altitude": "45.5", "sun_azimuth": "180.0"}})
    with patch("requests.get", return_value=resp):
        alt, az = get_sun_position(51.0, 0.0, "2025-06-01", "12:00:00")
    assert alt == 45.5
    assert az == 180.0


def test_get_sun_position_success_flat():
    # Data at root level (no "astronomy" wrapper)
    resp = _mock_resp(200, {"sun_altitude": "30.0", "sun_azimuth": "90.0"})
    with patch("requests.get", return_value=resp):
        alt, az = get_sun_position(51.0, 0.0, "2025-06-01", "09:00:00")
    assert alt == 30.0
    assert az == 90.0


def test_get_sun_position_api_error():
    resp = _mock_resp(500)
    with patch("requests.get", return_value=resp):
        with pytest.raises(HTTPException) as exc:
            get_sun_position(51.0, 0.0, "2025-06-01", "12:00:00")
    assert exc.value.status_code == 502


def test_get_sun_position_missing_keys():
    resp = _mock_resp(200, {"astronomy": {}})
    with patch("requests.get", return_value=resp):
        with pytest.raises(HTTPException) as exc:
            get_sun_position(51.0, 0.0, "2025-06-01", "12:00:00")
    assert exc.value.status_code == 502


def test_get_sun_position_bad_value_type():
    resp = _mock_resp(200, {"astronomy": {"sun_altitude": None, "sun_azimuth": "90"}})
    with patch("requests.get", return_value=resp):
        with pytest.raises(HTTPException) as exc:
            get_sun_position(51.0, 0.0, "2025-06-01", "12:00:00")
    assert exc.value.status_code == 502
