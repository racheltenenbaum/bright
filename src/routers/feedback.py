import logging
import os

import requests
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.auth import get_current_user
from src.database import get_db
from src.models import Feedback, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

# Feedback emails go through Resend's HTTP API rather than raw SMTP — Railway
# blocks outbound SMTP ports entirely (confirmed via a production
# "OSError: [Errno 101] Network is unreachable" trying to reach
# smtp.gmail.com:587), so no SMTP credentials could ever have worked here.
# An HTTPS API call has no such restriction.
_RESEND_API_KEY = os.getenv("RESEND_API_KEY")
_FEEDBACK_EMAIL = os.getenv("FEEDBACK_EMAIL")
_RESEND_FROM = "onboarding@resend.dev"  # Resend's default sender — no domain verification needed


class FeedbackRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("message cannot be blank")
        return v.strip()


def _send_feedback_email(message: str, from_email: str) -> None:
    if not all([_RESEND_API_KEY, _FEEDBACK_EMAIL]):
        logger.warning(
            "Feedback email skipped: missing Resend env var(s) (api_key=%s feedback_email=%s)",
            bool(_RESEND_API_KEY), bool(_FEEDBACK_EMAIL),
        )
        return
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {_RESEND_API_KEY}"},
        json={
            "from": _RESEND_FROM,
            "to": _FEEDBACK_EMAIL,
            "subject": "bright - app feedback",
            "text": f"From: {from_email}\n\n{message}",
        },
        timeout=10,
    )
    resp.raise_for_status()


@router.post("")
def submit_feedback(
    body: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = Feedback(
        user_id=current_user.id,
        from_email=current_user.email,
        message=body.message,
    )
    db.add(entry)
    db.commit()

    try:
        _send_feedback_email(body.message, current_user.email)
    except Exception:
        logger.exception("Failed to send feedback email")

    return {"ok": True}
