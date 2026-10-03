from datetime import datetime
from unittest.mock import patch

import pytest

from src.models import RegionNotifyRequest

TOKEN = "test-admin-token"
HEADERS = {"X-Admin-Token": TOKEN}


@pytest.fixture(autouse=True)
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", TOKEN)
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")


def _add_request(db, user, lat, lng, created_at, **kwargs):
    entry = RegionNotifyRequest(
        user_id=user.id, email=user.email, lat=lat, lng=lng, created_at=created_at, **kwargs,
    )
    db.add(entry)
    db.commit()
    return entry


# --- auth -------------------------------------------------------------------

def test_region_requests_missing_token_rejected(client):
    assert client.get("/admin/region-requests").status_code == 401


def test_region_requests_wrong_token_rejected(client):
    response = client.get("/admin/region-requests", headers={"X-Admin-Token": "nope"})
    assert response.status_code == 401


def test_region_requests_disabled_when_token_not_configured(client, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN")
    # Even a request sending an empty token must not get through when the
    # server has none configured.
    response = client.get("/admin/region-requests", headers={"X-Admin-Token": ""})
    assert response.status_code == 503


def test_region_requests_user_jwt_not_enough(client, auth_headers):
    assert client.get("/admin/region-requests", headers=auth_headers).status_code == 401


# --- GET /admin/region-requests ---------------------------------------------

def test_region_requests_lists_all_oldest_first(client, db, test_user):
    _add_request(db, test_user, 48.77, 9.21, datetime(2026, 9, 30, 7, 0))
    _add_request(db, test_user, 52.52, 13.40, datetime(2026, 10, 1, 8, 0), fulfilled=True)

    response = client.get("/admin/region-requests", headers=HEADERS)

    assert response.status_code == 200
    rows = response.json()["requests"]
    assert [(r["lat"], r["lng"]) for r in rows] == [(48.77, 9.21), (52.52, 13.40)]
    assert rows[0]["user_id"] == test_user.id
    assert rows[0]["fulfilled"] is False
    assert rows[1]["fulfilled"] is True
    assert rows[0]["notified"] is False
    assert rows[0]["created_at"].startswith("2026-09-30T07:00")


def test_region_requests_does_not_expose_user_email(client, db, test_user):
    _add_request(db, test_user, 48.77, 9.21, datetime(2026, 9, 30, 7, 0))
    response = client.get("/admin/region-requests", headers=HEADERS)
    row = response.json()["requests"][0]
    assert "email" not in row
    assert test_user.email not in response.text


def test_region_requests_since_filter(client, db, test_user):
    _add_request(db, test_user, 1.0, 1.0, datetime(2026, 9, 30, 7, 0))
    _add_request(db, test_user, 2.0, 2.0, datetime(2026, 10, 2, 7, 0))

    response = client.get(
        "/admin/region-requests", params={"since": "2026-10-01T00:00:00"}, headers=HEADERS,
    )

    rows = response.json()["requests"]
    assert [r["lat"] for r in rows] == [2.0]


def test_region_requests_marks_points_inside_covered_regions(client, db, test_user):
    _add_request(db, test_user, 48.2082, 16.3738, datetime(2026, 9, 30, 7, 0))  # Vienna
    _add_request(db, test_user, 48.1374, 11.5755, datetime(2026, 9, 30, 8, 0))  # Munich
    _add_request(db, test_user, 48.7735, 9.2093, datetime(2026, 9, 30, 9, 0))   # Stuttgart

    rows = client.get("/admin/region-requests", headers=HEADERS).json()["requests"]

    assert rows[0]["covered_region"] == "vienna"
    assert rows[1]["covered_region"] is None
    assert rows[2]["covered_region"] == "stuttgart"


# --- POST /admin/email ------------------------------------------------------

def test_admin_email_requires_token(client):
    response = client.post("/admin/email", json={"subject": "s", "text": "t"})
    assert response.status_code == 401


def test_admin_email_sends_to_configured_admin_only(client):
    with patch("src.routers.admin.send_email") as mock_send:
        response = client.post(
            "/admin/email", json={"subject": "Daily report", "text": "hello"}, headers=HEADERS,
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_send.assert_called_once_with("admin@example.com", "Daily report", "hello")


def test_admin_email_ignores_recipient_in_body(client):
    with patch("src.routers.admin.send_email") as mock_send:
        client.post(
            "/admin/email",
            json={"subject": "s", "text": "t", "to": "someone-else@example.com"},
            headers=HEADERS,
        )
    assert mock_send.call_args.args[0] == "admin@example.com"


def test_admin_email_503_when_admin_email_not_configured(client, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL")
    with patch("src.routers.admin.send_email") as mock_send:
        response = client.post("/admin/email", json={"subject": "s", "text": "t"}, headers=HEADERS)
    assert response.status_code == 503
    mock_send.assert_not_called()


def test_admin_email_502_when_send_fails(client):
    with patch("src.routers.admin.send_email", side_effect=RuntimeError("sendgrid down")):
        response = client.post("/admin/email", json={"subject": "s", "text": "t"}, headers=HEADERS)
    assert response.status_code == 502
