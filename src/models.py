from sqlalchemy import Column, Index, Integer, String, Float, Double, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from src.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    pref_max_detour = Column(Integer, nullable=False, default=30, server_default="30")
    pref_mode = Column(String(10), nullable=False, default="sun", server_default="sun")
    pref_map_controls = Column(Boolean, nullable=False, default=False, server_default="0")
    pref_map_type = Column(String(20), nullable=False, default="roadmap", server_default="roadmap")

    routes = relationship("Route", back_populates="user")
    spots = relationship("Spot", back_populates="user")
    feedback = relationship("Feedback", back_populates="user")


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    start_lat = Column(Float, nullable=False)
    start_lng = Column(Float, nullable=False)
    end_lat = Column(Float, nullable=False)
    end_lng = Column(Float, nullable=False)
    start_address = Column(String(512), nullable=True)
    end_address = Column(String(512), nullable=True)
    preference = Column(String(10), nullable=True)
    share_token = Column(String(36), nullable=True, unique=True, index=True)
    route_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="routes")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_email = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="feedback")


class RegionNotifyRequest(Base):
    __tablename__ = "region_notify_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email = Column(String(255), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    fulfilled = Column(Boolean, nullable=False, default=False, server_default="0")
    notified = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow)


class OsmBuilding(Base):
    """Bulk-imported building footprint + height, used instead of a live
    Overpass query for regions we've pre-loaded (see src/routers/shadow_analyze.py
    _region_for_bbox). Bounding-box columns mirror the simple rectangle-filter
    bbox queries already used throughout this codebase — no spatial extension
    needed.
    """
    __tablename__ = "osm_buildings"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(String(20), nullable=False, index=True)  # e.g. "vienna", "nyc"
    source = Column(String(20), nullable=False)  # e.g. "osm", "vienna_wfs"
    min_lat = Column(Float, nullable=False, index=True)
    max_lat = Column(Float, nullable=False, index=True)
    min_lng = Column(Float, nullable=False, index=True)
    max_lng = Column(Float, nullable=False, index=True)
    footprint = Column(Text, nullable=False)  # JSON: [[lat, lng], ...]
    height = Column(Float, nullable=False)

    # The bbox lookup filters all 4 columns as an AND of ranges — a bare
    # single-column index per column can't be used together for that (MySQL
    # picks one, typically region, then scans/filters every remaining row in
    # that region: confirmed via EXPLAIN scanning ~2M rows for LA). This
    # composite index lets a range scan on min_lat/max_lat (within the
    # region) replace that full scan, with min_lng/max_lng applied as a
    # cheap filter over the much smaller result — MySQL's optimizer doesn't
    # pick this automatically (tried; cost estimate favors the full scan
    # even after ANALYZE TABLE), so the query forces it explicitly. A second
    # composite on (region, min_lng, max_lng) for index-merge was tried too
    # and measured slower than the plain scan, so it's not included.
    __table_args__ = (
        Index("ix_osm_buildings_region_lat", "region", "min_lat", "max_lat"),
    )


class OsmRoad(Base):
    """Bulk-imported road edge, used instead of a live Overpass query for
    regions we've pre-loaded (see src/routing.py _region_for_bbox). One row
    per directed edge (already split from ways the same way build_graph does
    it), so local lookups can build the routing graph directly without
    reparsing raw OSM node/way elements. Bounding-box columns mirror the
    simple rectangle-filter bbox queries already used throughout this
    codebase — no spatial extension needed.
    """
    __tablename__ = "osm_roads"

    # Double, not Float: single-precision Float only holds ~7 significant
    # digits, which quantizes a latitude like 34.0922544 down to about
    # 34.0923 — an ~11m grid. Since build_graph_from_edges uses these exact
    # coordinates as graph node identity, that quantization let genuinely
    # distinct points collapse onto the same node, producing snakey/staircase
    # street shapes and occasional physically-impossible "shortcuts"
    # (a computed path shorter than the straight-line distance between its
    # own endpoints).
    id = Column(Integer, primary_key=True, index=True)
    region = Column(String(20), nullable=False, index=True)  # e.g. "la"
    min_lat = Column(Double, nullable=False, index=True)
    max_lat = Column(Double, nullable=False, index=True)
    min_lng = Column(Double, nullable=False, index=True)
    max_lng = Column(Double, nullable=False, index=True)
    from_lat = Column(Double, nullable=False)
    from_lng = Column(Double, nullable=False)
    to_lat = Column(Double, nullable=False)
    to_lng = Column(Double, nullable=False)
    distance_m = Column(Float, nullable=False)
    oneway = Column(Boolean, nullable=False, default=False)

    # Same reasoning as OsmBuilding above — confirmed via EXPLAIN scanning
    # ~2.7M rows for an LA bbox lookup without this, forced explicitly in
    # the query since the optimizer doesn't pick it on its own.
    __table_args__ = (
        Index("ix_osm_roads_region_lat", "region", "min_lat", "max_lat"),
    )


class Spot(Base):
    __tablename__ = "spots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    address = Column(String(512), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    icon = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    place_id = Column(String(255), nullable=True)
    city = Column(String(255), nullable=False, server_default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    share_token = Column(String(36), nullable=True, unique=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="spots")
