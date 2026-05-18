import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth import get_current_user
from src.database import get_db
from src.models import Route, User
from src.schemas import RouteCreate, RouteResponse, ShareTokenResponse, SharedRouteResponse

router = APIRouter(prefix="/routes", tags=["routes"])


@router.post("", response_model=RouteResponse, status_code=201)
def save_route(
    body: RouteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    route = Route(**body.model_dump(), user_id=current_user.id)
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


@router.get("", response_model=list[RouteResponse])
def get_routes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Route).filter(Route.user_id == current_user.id).order_by(Route.created_at.desc()).all()


@router.delete("/{route_id}", status_code=204)
def delete_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Route).filter(Route.id == route_id, Route.user_id == current_user.id).delete()
    db.commit()


@router.post("/{route_id}/share", response_model=ShareTokenResponse)
def share_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    route = db.query(Route).filter(Route.id == route_id, Route.user_id == current_user.id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    if not route.share_token:
        route.share_token = str(uuid.uuid4())
        db.commit()
        db.refresh(route)
    return {"share_token": route.share_token}



share_router = APIRouter(prefix="/share", tags=["share"])


@share_router.get("/{token}", response_model=SharedRouteResponse)
def get_shared_route(token: str, db: Session = Depends(get_db)):
    route = db.query(Route).filter(Route.share_token == token).first()
    if not route:
        raise HTTPException(status_code=404, detail="Shared route not found")
    return route
