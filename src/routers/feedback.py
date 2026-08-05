import os
import smtplib
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from src.auth import get_current_user
from src.database import get_db
from src.models import Feedback, User

router = APIRouter(prefix="/feedback", tags=["feedback"])

_SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
_SMTP_USER = os.getenv("SMTP_USER")
_SMTP_PASS = os.getenv("SMTP_PASS")
_FEEDBACK_EMAIL = os.getenv("FEEDBACK_EMAIL")


class FeedbackRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("message cannot be blank")
        return v.strip()


def _send_feedback_email(message: str, from_email: str) -> None:
    if not all([_SMTP_USER, _SMTP_PASS, _FEEDBACK_EMAIL]):
        return
    msg = MIMEText(f"From: {from_email}\n\n{message}")
    msg["Subject"] = "bright - app feedback"
    msg["From"] = _SMTP_USER
    msg["To"] = _FEEDBACK_EMAIL
    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
        server.starttls()
        server.login(_SMTP_USER, _SMTP_PASS)
        server.send_message(msg)


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
        pass

    return {"ok": True}
