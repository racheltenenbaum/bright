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


def send_email(
    to: str, subject: str, text: str, html: str | None = None, bcc: str | None = None,
) -> None:
    if not _SENDGRID_API_KEY or not _SENDGRID_FROM:
        logger.warning(
            "Email skipped: missing SendGrid credentials (api_key=%s from=%s)",
            bool(_SENDGRID_API_KEY), bool(_SENDGRID_FROM),
        )
        return
    # SendGrid requires text/plain before text/html; clients that can't
    # render HTML fall back to the plain part.
    content = [{"type": "text/plain", "value": text}]
    if html is not None:
        content.append({"type": "text/html", "value": html})
    personalization = {"to": [{"email": to}]}
    # SendGrid rejects a message whose bcc repeats an address from "to".
    if bcc and bcc.lower() != to.lower():
        personalization["bcc"] = [{"email": bcc}]
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {_SENDGRID_API_KEY}"},
        json={
            "personalizations": [personalization],
            "from": {"email": _SENDGRID_FROM},
            "subject": subject,
            "content": content,
            # SendGrid rewrites links to its own click-tracking domain by
            # default, which breaks Universal Links / App Links — the OS
            # only recognizes a tap as opening our app if the tapped link's
            # own domain matches our verified one, not a domain it redirects
            # through afterward. Password-reset links must stay literal.
            "tracking_settings": {"click_tracking": {"enable": False}},
        },
        timeout=10,
    )
    resp.raise_for_status()
