from fastapi import APIRouter
from pydantic import BaseModel

from src.regions import REGION_BOUNDS, REGION_DISPLAY_NAMES

router = APIRouter(prefix="/regions", tags=["regions"])


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
