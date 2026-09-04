from unittest.mock import patch, MagicMock

from src.models import Feedback


def test_feedback_success(client, auth_headers, db):
    with patch("src.routers.feedback._send_feedback_email") as mock_send:
        response = client.post("/feedback", json={"message": "Love the app!"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_send.assert_called_once()
    assert db.query(Feedback).count() == 1
    entry = db.query(Feedback).first()
    assert entry.message == "Love the app!"


def test_feedback_saved_to_db_even_if_email_fails(client, auth_headers, db):
    with patch("src.routers.feedback._send_feedback_email", side_effect=Exception("SMTP error")):
        response = client.post("/feedback", json={"message": "test message"}, headers=auth_headers)
    assert response.status_code == 200
    assert db.query(Feedback).count() == 1


def test_feedback_empty_message_rejected(client, auth_headers):
    response = client.post("/feedback", json={"message": "   "}, headers=auth_headers)
    assert response.status_code == 422


def test_feedback_unauthenticated(client):
    response = client.post("/feedback", json={"message": "test"})
    assert response.status_code == 401


def test_feedback_strips_whitespace(client, auth_headers, db):
    with patch("src.routers.feedback._send_feedback_email") as mock_send:
        response = client.post("/feedback", json={"message": "  great app  "}, headers=auth_headers)
    assert response.status_code == 200
    call_args = mock_send.call_args[0]
    assert call_args[0] == "great app"
    assert db.query(Feedback).first().message == "great app"


def test_send_feedback_email_resend_configured():
    """Exercises the Resend HTTP API sending path when credentials are set.

    Uses Resend instead of raw SMTP because Railway blocks outbound SMTP
    ports entirely (confirmed via OSError: [Errno 101] Network is
    unreachable in production logs) — an HTTPS API call has no such
    restriction.
    """
    import src.routers.feedback as fb_module
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    with patch.object(fb_module, "_RESEND_API_KEY", "re_test_key"), \
         patch.object(fb_module, "_FEEDBACK_EMAIL", "dest@example.com"), \
         patch("requests.post", return_value=mock_resp) as mock_post:
        fb_module._send_feedback_email("hello", "sender@example.com")
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer re_test_key"
    assert kwargs["json"]["to"] == "dest@example.com"
    assert kwargs["json"]["from"] == fb_module._RESEND_FROM
    assert "sender@example.com" in kwargs["json"]["text"]
    assert "hello" in kwargs["json"]["text"]
    mock_resp.raise_for_status.assert_called_once()


def test_send_feedback_email_no_credentials_is_noop():
    """When Resend credentials are missing, _send_feedback_email returns without error."""
    import src.routers.feedback as fb_module
    with patch.object(fb_module, "_RESEND_API_KEY", None), \
         patch.object(fb_module, "_FEEDBACK_EMAIL", None), \
         patch("requests.post") as mock_post:
        fb_module._send_feedback_email("hello", "sender@example.com")
    mock_post.assert_not_called()
