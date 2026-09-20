import logging
import os

import requests

logger = logging.getLogger(__name__)

# SendGrid, not Resend: Resend's free tier can only send to the account
# owner's own verified address until a full domain is verified (DNS records
# required). SendGrid's Single Sender Verification lets a single email
# address be verified (just a confirmation-link click) and then send to any
# recipient — no domain needed, which is what emails to arbitrary users
# (password reset, region-notify) actually require.
_SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
_SENDGRID_FROM = os.getenv("SENDGRID_FROM_EMAIL")


def send_email(to: str, subject: str, text: str) -> None:
    if not _SENDGRID_API_KEY or not _SENDGRID_FROM:
        logger.warning(
            "Email skipped: missing SendGrid credentials (api_key=%s from=%s)",
            bool(_SENDGRID_API_KEY), bool(_SENDGRID_FROM),
        )
        return
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {_SENDGRID_API_KEY}"},
        json={
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": _SENDGRID_FROM},
            "subject": subject,
            "content": [{"type": "text/plain", "value": text}],
        },
        timeout=10,
    )
    resp.raise_for_status()
