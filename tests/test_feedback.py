from unittest.mock import patch, MagicMock


def test_feedback_success(client, auth_headers):
    with patch("src.routers.feedback._send_feedback_email") as mock_send:
        response = client.post("/feedback", json={"message": "Love the app!"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_send.assert_called_once()


def test_feedback_empty_message_rejected(client, auth_headers):
    response = client.post("/feedback", json={"message": "   "}, headers=auth_headers)
    assert response.status_code == 422


def test_feedback_unauthenticated(client):
    response = client.post("/feedback", json={"message": "test"})
    assert response.status_code == 401


def test_feedback_email_failure_still_returns_200(client, auth_headers):
    with patch("src.routers.feedback._send_feedback_email", side_effect=Exception("SMTP error")):
        response = client.post("/feedback", json={"message": "test message"}, headers=auth_headers)
    assert response.status_code == 200


def test_feedback_strips_whitespace(client, auth_headers):
    with patch("src.routers.feedback._send_feedback_email") as mock_send:
        response = client.post("/feedback", json={"message": "  great app  "}, headers=auth_headers)
    assert response.status_code == 200
    call_args = mock_send.call_args[0]
    assert call_args[0] == "great app"


def test_send_feedback_email_smtp_configured():
    """Exercises the SMTP sending path when credentials are set."""
    import src.routers.feedback as fb_module
    mock_server = MagicMock()
    mock_smtp_cls = MagicMock(return_value=__import__("contextlib").nullcontext(mock_server))
    with patch.object(fb_module, "_SMTP_USER", "user@example.com"), \
         patch.object(fb_module, "_SMTP_PASS", "secret"), \
         patch.object(fb_module, "_FEEDBACK_EMAIL", "dest@example.com"), \
         patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        fb_module._send_feedback_email("hello", "sender@example.com")
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@example.com", "secret")
    mock_server.send_message.assert_called_once()


def test_send_feedback_email_no_credentials_is_noop():
    """When SMTP credentials are missing, _send_feedback_email returns without error."""
    import src.routers.feedback as fb_module
    with patch.object(fb_module, "_SMTP_USER", None), \
         patch.object(fb_module, "_SMTP_PASS", None), \
         patch.object(fb_module, "_FEEDBACK_EMAIL", None), \
         patch("smtplib.SMTP") as mock_smtp:
        fb_module._send_feedback_email("hello", "sender@example.com")
    mock_smtp.assert_not_called()
