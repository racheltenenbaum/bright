"""Token-protected admin endpoints for automated jobs (e.g. the daily
region-request report routine) — not for app users. Auth is a shared secret
in the X-Admin-Token header rather than a user JWT, so a scheduled job can
call these without holding any user account's credentials.
"""
import logging
import os
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import get_db
from src.email_client import send_email
from src.models import RegionNotifyRequest
from src.regions import region_for_bbox

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    # Read at call time (not module load) so the token can be rotated via a
    # Railway env var change + restart without code changes, and so an unset
    # token disables these endpoints entirely instead of matching "".
    expected = os.getenv("ADMIN_API_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="Admin API not configured")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token")


class RegionRequestOut(BaseModel):
    # Deliberately no email: the report routine only needs locations and a
    # stable user id to spot repeat requests from the same person.
    id: int
    user_id: int
    lat: float
    lng: float
    fulfilled: bool
    notified: bool
    created_at: datetime
    covered_region: str | None


class RegionRequestListResponse(BaseModel):
    requests: list[RegionRequestOut]


@router.get(
    "/region-requests",
    response_model=RegionRequestListResponse,
    dependencies=[Depends(require_admin_token)],
)
def list_region_requests(since: datetime | None = None, db: Session = Depends(get_db)):
    query = db.query(RegionNotifyRequest)
    if since is not None:
        query = query.filter(RegionNotifyRequest.created_at >= since)
    rows = query.order_by(RegionNotifyRequest.id).all()
    return RegionRequestListResponse(requests=[
        RegionRequestOut(
            id=r.id,
            user_id=r.user_id,
            lat=r.lat,
            lng=r.lng,
            fulfilled=r.fulfilled,
            notified=r.notified,
            created_at=r.created_at,
            covered_region=region_for_bbox(r.lat, r.lng, r.lat, r.lng),
        )
        for r in rows
    ])


class AdminEmailRequest(BaseModel):
    subject: str
    text: str


@router.post("/email", dependencies=[Depends(require_admin_token)])
def email_admin(body: AdminEmailRequest):
    # Recipient is fixed server-side, never taken from the request, so a
    # leaked admin token can't be used to send mail to arbitrary people.
    to = os.getenv("ADMIN_EMAIL")
    if not to:
        raise HTTPException(status_code=503, detail="ADMIN_EMAIL not configured")
    try:
        send_email(to, body.subject, body.text)
    except Exception:
        logger.exception("Failed to send admin email")
        raise HTTPException(status_code=502, detail="Failed to send email")
    return {"ok": True}
