from unittest.mock import MagicMock, patch

import src.email_client as email_client


def _mock_resp_ok():
    m = MagicMock()
    m.raise_for_status = MagicMock()
    return m


def test_send_email_success_posts_expected_payload():
    mock_resp = _mock_resp_ok()
    with patch.object(email_client, "_SENDGRID_API_KEY", "SG_test_key"), \
         patch.object(email_client, "_SENDGRID_FROM", "sender@example.com"), \
         patch("requests.post", return_value=mock_resp) as mock_post:
        email_client.send_email("someone@example.com", "Subject line", "Body text")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.sendgrid.com/v3/mail/send"
    assert kwargs["headers"]["Authorization"] == "Bearer SG_test_key"
    body = kwargs["json"]
    assert body["personalizations"] == [{"to": [{"email": "someone@example.com"}]}]
    assert body["from"] == {"email": "sender@example.com"}
    assert body["subject"] == "Subject line"
    assert body["content"] == [{"type": "text/plain", "value": "Body text"}]
    # Click tracking must stay off — a wrapped link would break Universal
    # Links / App Links for password-reset emails.
    assert body["tracking_settings"] == {"click_tracking": {"enable": False}}
    mock_resp.raise_for_status.assert_called_once()


def test_send_email_missing_api_key_is_noop():
    with patch.object(email_client, "_SENDGRID_API_KEY", None), \
         patch.object(email_client, "_SENDGRID_FROM", "sender@example.com"), \
         patch("requests.post") as mock_post:
        email_client.send_email("someone@example.com", "Subject", "Body")
    mock_post.assert_not_called()


def test_send_email_missing_from_address_is_noop():
    with patch.object(email_client, "_SENDGRID_API_KEY", "SG_test_key"), \
         patch.object(email_client, "_SENDGRID_FROM", None), \
         patch("requests.post") as mock_post:
        email_client.send_email("someone@example.com", "Subject", "Body")
    mock_post.assert_not_called()


def test_send_email_propagates_http_errors():
    import requests as requests_module

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests_module.HTTPError("boom")
    with patch.object(email_client, "_SENDGRID_API_KEY", "SG_test_key"), \
         patch.object(email_client, "_SENDGRID_FROM", "sender@example.com"), \
         patch("requests.post", return_value=mock_resp):
        try:
            email_client.send_email("someone@example.com", "Subject", "Body")
            assert False, "expected HTTPError to propagate"
        except requests_module.HTTPError:
            pass


def test_send_email_with_html_sends_plain_text_first_then_html():
    mock_resp = _mock_resp_ok()
    with patch.object(email_client, "_SENDGRID_API_KEY", "SG_test_key"), \
         patch.object(email_client, "_SENDGRID_FROM", "sender@example.com"), \
         patch("requests.post", return_value=mock_resp) as mock_post:
        email_client.send_email("someone@example.com", "Subject", "Body text", html="<p>Body</p>")

    # SendGrid requires text/plain before text/html; clients without HTML
    # support fall back to the plain part.
    assert mock_post.call_args.kwargs["json"]["content"] == [
        {"type": "text/plain", "value": "Body text"},
        {"type": "text/html", "value": "<p>Body</p>"},
    ]


def test_send_email_with_bcc_adds_bcc_to_personalization():
    mock_resp = _mock_resp_ok()
    with patch.object(email_client, "_SENDGRID_API_KEY", "SG_test_key"), \
         patch.object(email_client, "_SENDGRID_FROM", "sender@example.com"), \
         patch("requests.post", return_value=mock_resp) as mock_post:
        email_client.send_email("someone@example.com", "S", "B", bcc="admin@example.com")

    assert mock_post.call_args.kwargs["json"]["personalizations"] == [
        {"to": [{"email": "someone@example.com"}], "bcc": [{"email": "admin@example.com"}]},
    ]


def test_send_email_skips_bcc_matching_recipient():
    # SendGrid rejects a message whose bcc repeats an address from "to".
    mock_resp = _mock_resp_ok()
    with patch.object(email_client, "_SENDGRID_API_KEY", "SG_test_key"), \
         patch.object(email_client, "_SENDGRID_FROM", "sender@example.com"), \
         patch("requests.post", return_value=mock_resp) as mock_post:
        email_client.send_email("Admin@Example.com", "S", "B", bcc="admin@example.com")

    assert mock_post.call_args.kwargs["json"]["personalizations"] == [
        {"to": [{"email": "Admin@Example.com"}]},
    ]
