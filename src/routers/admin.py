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
from src.models import RegionNotifyRequest, User
from src.region_emails import build_region_live_email
from src.regions import REGION_DISPLAY_NAMES, region_for_bbox

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


class NotifyCoveredRequest(BaseModel):
    # Defaults to a dry run so a bare call can never email anyone.
    dry_run: bool = True
    # Send one sample email per city to ADMIN_EMAIL instead of to users,
    # without marking anything — for checking the email before a real send.
    preview_to_admin: bool = False


class PendingNotification(BaseModel):
    user_id: int
    region: str
    request_count: int


class FailedNotification(BaseModel):
    user_id: int
    region: str


class NotifyCoveredResponse(BaseModel):
    dry_run: bool
    notifications: list[PendingNotification]
    sent: int = 0
    previewed: int = 0
    failed: list[FailedNotification] = []


@router.post(
    "/region-requests/notify-covered",
    response_model=NotifyCoveredResponse,
    dependencies=[Depends(require_admin_token)],
)
def notify_covered_region_requests(body: NotifyCoveredRequest, db: Session = Depends(get_db)):
    """Email everyone whose notify-me request is now inside a covered region.

    People often tap "notify me" several times from different spots in the
    same city, so requests are grouped per (user, region): one email per
    person per city, and every request in that group is marked notified.
    A group that already has a notified request is never emailed again.
    """
    groups: dict[tuple[int, str], list[RegionNotifyRequest]] = {}
    for row in db.query(RegionNotifyRequest).order_by(RegionNotifyRequest.id):
        region = region_for_bbox(row.lat, row.lng, row.lat, row.lng)
        if region is not None:
            groups.setdefault((row.user_id, region), []).append(row)

    pending: list[tuple[int, str, list[RegionNotifyRequest]]] = []
    for (user_id, region), rows in groups.items():
        unnotified = [r for r in rows if not r.notified]
        if not unnotified:
            continue
        if len(unnotified) < len(rows):
            # Already emailed about this city — absorb the newer requests
            # silently instead of sending a second email.
            if not body.dry_run and not body.preview_to_admin:
                for r in unnotified:
                    r.notified = True
                    r.fulfilled = True
                db.commit()
            continue
        pending.append((user_id, region, rows))

    response = NotifyCoveredResponse(
        dry_run=body.dry_run,
        notifications=[
            PendingNotification(user_id=u, region=reg, request_count=len(rows))
            for u, reg, rows in pending
        ],
    )
    if body.dry_run:
        return response

    if body.preview_to_admin:
        admin_email = os.getenv("ADMIN_EMAIL")
        if not admin_email:
            raise HTTPException(status_code=503, detail="ADMIN_EMAIL not configured")
        previewed_regions: set[str] = set()
        for user_id, region, _rows in pending:
            if region in previewed_regions:
                continue
            user = db.get(User, user_id)
            subject, text, html = build_region_live_email(
                user.first_name if user else None, REGION_DISPLAY_NAMES[region],
            )
            send_email(admin_email, f"[preview] {subject}", text, html=html)
            previewed_regions.add(region)
        response.previewed = len(previewed_regions)
        return response

    for user_id, region, rows in pending:
        user = db.get(User, user_id)
        to = user.email if user else rows[-1].email
        subject, text, html = build_region_live_email(
            user.first_name if user else None, REGION_DISPLAY_NAMES[region],
        )
        try:
            send_email(to, subject, text, html=html)
        except Exception:
            logger.exception("Failed to send region-live email (user %s, %s)", user_id, region)
            response.failed.append(FailedNotification(user_id=user_id, region=region))
            continue
        # Commit per person so a crash partway through can't re-email
        # anyone who was already sent their email.
        for r in rows:
            r.notified = True
            r.fulfilled = True
        db.commit()
        response.sent += 1
    return response
