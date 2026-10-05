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


# --- POST /admin/region-requests/notify-covered -----------------------------

from src.models import User

STUTTGART = (48.7735, 9.2093)
STUTTGART_2 = (48.7800, 9.1800)
VIENNA = (48.2082, 16.3738)
MUNICH = (48.1374, 11.5755)  # not covered
NOTIFY_URL = "/admin/region-requests/notify-covered"


def _user(db, first_name, email):
    user = User(first_name=first_name, email=email, hashed_password=None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _rows(db):
    db.expire_all()
    return db.query(RegionNotifyRequest).order_by(RegionNotifyRequest.id).all()


def test_notify_covered_requires_token(client):
    assert client.post(NOTIFY_URL, json={}).status_code == 401


def test_notify_covered_defaults_to_dry_run(client, db, test_user):
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30))
    with patch("src.routers.admin.send_email") as mock_send:
        response = client.post(NOTIFY_URL, json={}, headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["notifications"] == [
        {"user_id": test_user.id, "region": "stuttgart", "request_count": 1},
    ]
    assert body["sent"] == 0
    mock_send.assert_not_called()
    assert _rows(db)[0].notified is False


def test_notify_covered_groups_repeat_requests_in_one_city(client, db, test_user):
    for i, (lat, lng) in enumerate([STUTTGART, STUTTGART_2, STUTTGART]):
        _add_request(db, test_user, lat, lng, datetime(2026, 9, 30, i))

    body = client.post(NOTIFY_URL, json={"dry_run": True}, headers=HEADERS).json()

    assert body["notifications"] == [
        {"user_id": test_user.id, "region": "stuttgart", "request_count": 3},
    ]


def test_notify_covered_sends_one_email_per_user_per_city(client, db, test_user):
    other = _user(db, "Dana", "dana@example.com")
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30, 1))
    _add_request(db, test_user, *STUTTGART_2, datetime(2026, 9, 30, 2))
    _add_request(db, other, *STUTTGART, datetime(2026, 9, 30, 3))

    with patch("src.routers.admin.send_email") as mock_send:
        body = client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS).json()

    assert body["sent"] == 2
    assert sorted(c.args[0] for c in mock_send.call_args_list) == ["dana@example.com", "test@example.com"]
    dana_call = next(c for c in mock_send.call_args_list if c.args[0] == "dana@example.com")
    assert dana_call.args[2].startswith("Hi Dana,")
    assert "Stuttgart" in dana_call.args[1]
    assert "html" in dana_call.kwargs
    assert all(r.notified and r.fulfilled for r in _rows(db))


def test_notify_covered_never_emails_the_same_user_twice_for_a_city(client, db, test_user):
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30, 1))
    with patch("src.routers.admin.send_email"):
        client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS)

    # A later request in the same city must not trigger a second email.
    _add_request(db, test_user, *STUTTGART_2, datetime(2026, 10, 5, 1))
    with patch("src.routers.admin.send_email") as mock_send:
        body = client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS).json()

    mock_send.assert_not_called()
    assert body["notifications"] == []
    assert all(r.notified for r in _rows(db))


def test_notify_covered_emails_separately_for_different_cities(client, db, test_user):
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30, 1))
    _add_request(db, test_user, *VIENNA, datetime(2026, 9, 30, 2))

    with patch("src.routers.admin.send_email") as mock_send:
        body = client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS).json()

    assert body["sent"] == 2
    subjects = sorted(c.args[1] for c in mock_send.call_args_list)
    assert any("Stuttgart" in s for s in subjects) and any("Vienna" in s for s in subjects)


def test_notify_covered_ignores_uncovered_requests(client, db, test_user):
    _add_request(db, test_user, *MUNICH, datetime(2026, 9, 30, 1))

    with patch("src.routers.admin.send_email") as mock_send:
        body = client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS).json()

    mock_send.assert_not_called()
    assert body["notifications"] == []
    assert _rows(db)[0].notified is False


def test_notify_covered_send_failure_leaves_that_user_pending(client, db, test_user):
    other = _user(db, "Dana", "dana@example.com")
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30, 1))
    _add_request(db, other, *STUTTGART, datetime(2026, 9, 30, 2))

    def fail_for_test_user(to, subject, text, html=None, bcc=None):
        if to == "test@example.com":
            raise RuntimeError("sendgrid down")

    with patch("src.routers.admin.send_email", side_effect=fail_for_test_user):
        body = client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS).json()

    assert body["sent"] == 1
    assert body["failed"] == [{"user_id": test_user.id, "region": "stuttgart"}]
    rows = {r.user_id: r for r in _rows(db)}
    assert rows[test_user.id].notified is False
    assert rows[other.id].notified is True


def test_notify_covered_preview_sends_sample_to_admin_only(client, db, test_user):
    other = _user(db, "Dana", "dana@example.com")
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30, 1))
    _add_request(db, other, *STUTTGART, datetime(2026, 9, 30, 2))

    with patch("src.routers.admin.send_email") as mock_send:
        body = client.post(
            NOTIFY_URL, json={"dry_run": False, "preview_to_admin": True}, headers=HEADERS,
        ).json()

    # One sample per city, to the admin, and nothing marked as notified.
    assert [c.args[0] for c in mock_send.call_args_list] == ["admin@example.com"]
    assert body["sent"] == 0
    assert body["previewed"] == 1
    assert not any(r.notified for r in _rows(db))


def test_notify_covered_preview_503_without_admin_email(client, db, test_user, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL")
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30, 1))
    with patch("src.routers.admin.send_email") as mock_send:
        response = client.post(
            NOTIFY_URL, json={"dry_run": False, "preview_to_admin": True}, headers=HEADERS,
        )
    assert response.status_code == 503
    mock_send.assert_not_called()


def test_notify_covered_rerun_with_nothing_new_sends_nothing(client, db, test_user):
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30, 1))
    with patch("src.routers.admin.send_email"):
        client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS)

    with patch("src.routers.admin.send_email") as mock_send:
        body = client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS).json()

    mock_send.assert_not_called()
    assert body["notifications"] == []
    assert body["sent"] == 0


def test_notify_covered_bccs_admin_on_every_real_send(client, db, test_user):
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30, 1))
    with patch("src.routers.admin.send_email") as mock_send:
        client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS)
    assert mock_send.call_args.kwargs["bcc"] == "admin@example.com"


def test_notify_covered_sends_without_bcc_when_admin_email_unset(client, db, test_user, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL")
    _add_request(db, test_user, *STUTTGART, datetime(2026, 9, 30, 1))
    with patch("src.routers.admin.send_email") as mock_send:
        body = client.post(NOTIFY_URL, json={"dry_run": False}, headers=HEADERS).json()
    assert body["sent"] == 1
    assert mock_send.call_args.kwargs["bcc"] is None
