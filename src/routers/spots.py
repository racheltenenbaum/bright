from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth import get_current_user
from src.database import get_db
from src.models import Spot, User
from src.schemas import SpotCreate, SpotResponse

router = APIRouter(prefix="/spots", tags=["spots"])


@router.get("", response_model=list[SpotResponse])
def get_spots(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Spot).filter(Spot.user_id == current_user.id).order_by(Spot.created_at).all()


@router.post("", response_model=SpotResponse, status_code=201)
def create_spot(body: SpotCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    spot = Spot(**body.model_dump(), user_id=current_user.id)
    db.add(spot)
    db.commit()
    db.refresh(spot)
    return spot


@router.patch("/{spot_id}", response_model=SpotResponse)
def update_spot(spot_id: int, body: SpotCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    spot = db.query(Spot).filter(Spot.id == spot_id, Spot.user_id == current_user.id).first()
    if not spot:
        raise HTTPException(status_code=404, detail="Spot not found")
    for field, value in body.model_dump().items():
        setattr(spot, field, value)
    db.commit()
    db.refresh(spot)
    return spot


@router.delete("/{spot_id}", status_code=204)
def delete_spot(spot_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.query(Spot).filter(Spot.id == spot_id, Spot.user_id == current_user.id).delete()
    db.commit()
