import logging
import os

import requests
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.auth import get_current_user
from src.database import get_db
from src.models import RegionNotifyRequest, User
from src.regions import REGION_BOUNDS, REGION_DISPLAY_NAMES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regions", tags=["regions"])

# Same Resend HTTP API used for feedback emails (src/routers/feedback.py) —
# Railway blocks outbound SMTP entirely, so this is the only send path that works.
_RESEND_API_KEY = os.getenv("RESEND_API_KEY")
_RESEND_FROM = "onboarding@resend.dev"


class RegionBounds(BaseModel):
    south: float
    west: float
    north: float
    east: float


class Region(BaseModel):
    id: str
    name: str
    bounds: RegionBounds


class RegionListResponse(BaseModel):
    regions: list[Region]


class NotifyMeRequest(BaseModel):
    lat: float
    lng: float


def _send_notify_confirmation_email(to_email: str) -> None:
    if not _RESEND_API_KEY:
        logger.warning("Notify-me confirmation email skipped: missing RESEND_API_KEY")
        return
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {_RESEND_API_KEY}"},
        json={
            "from": _RESEND_FROM,
            "to": to_email,
            "subject": "bright - you're on the list",
            "text": "Thanks for your interest! We'll email you as soon as bright covers your area.",
        },
        timeout=10,
    )
    resp.raise_for_status()


@router.get("", response_model=RegionListResponse)
def list_regions():
    regions = [
        Region(
            id=region_id,
            name=REGION_DISPLAY_NAMES[region_id],
            bounds=RegionBounds(south=s, west=w, north=n, east=e),
        )
        for region_id, (s, w, n, e) in REGION_BOUNDS.items()
    ]
    return RegionListResponse(regions=regions)


@router.post("/notify")
def notify_me(
    body: NotifyMeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = RegionNotifyRequest(
        user_id=current_user.id,
        email=current_user.email,
        lat=body.lat,
        lng=body.lng,
    )
    db.add(entry)
    db.commit()

    try:
        _send_notify_confirmation_email(current_user.email)
    except Exception:
        logger.exception("Failed to send notify-me confirmation email")

    return {"ok": True}
