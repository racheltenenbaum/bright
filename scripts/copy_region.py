"""Copy one region's imported city data (osm_buildings + osm_roads) from one
database to another — e.g. production → staging so staging routes like
production, or staging → production when a city is released.

Purely additive: it only INSERTs into the destination, never deletes or
updates. Each batch commits on its own, so a dropped connection (common over
Railway's public proxy on multi-million-row copies) loses at most one batch.
Re-running the same command resumes: rows are copied in source id order, so
the destination's row count for the region says how far the last run got.
Before resuming, the last copied row is checked against the source row it
should match, and the script stops if they differ (the destination holds
data from some other import, which this script won't mix with).

Usage (run from repo root):
    python scripts/copy_region.py --from-url "$SRC_URL" --to-url "$DST_URL" --region vienna
    python scripts/copy_region.py ... --region berlin --tables osm_roads
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# src.database refuses to import without DATABASE_URL, though this script
# never uses the app's own engine — only the two URLs passed in.
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from src.database import _normalize_db_url
from src.models import OsmBuilding, OsmRoad

TABLES = {t.name: t for t in (OsmBuilding.__table__, OsmRoad.__table__)}
BATCH_SIZE = 5_000
MAX_RETRIES = 5


def _data_columns(table):
    return [c for c in table.columns if c.name != "id"]


def _count(engine: Engine, table, region: str) -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table).where(table.c.region == region)).scalar()


def _row_at(engine: Engine, table, region: str, offset: int):
    """The region's row at this position in id order (id included)."""
    with engine.connect() as conn:
        return conn.execute(
            select(table).where(table.c.region == region).order_by(table.c.id).offset(offset).limit(1)
        ).one()


def _same_data(table, a, b) -> bool:
    return all(getattr(a, c.name) == getattr(b, c.name) for c in _data_columns(table))


def copy_table(src: Engine, dst: Engine, table, region: str, batch_size: int = BATCH_SIZE) -> int:
    """Copy the region's rows not yet in dst; returns how many were copied."""
    total = _count(src, table, region)
    done = _count(dst, table, region)
    if done > total:
        sys.exit(f"{table.name}/{region}: destination has {done} rows but source only {total} — "
                 "it holds data from another import; not touching it.")
    if done == total:
        print(f"{table.name}/{region}: already complete ({total} rows)")
        return 0

    last_id = 0
    if done:
        src_last = _row_at(src, table, region, done - 1)
        dst_last = _row_at(dst, table, region, done - 1)
        if not _same_data(table, src_last, dst_last):
            sys.exit(f"{table.name}/{region}: destination's row {done} doesn't match the source — "
                     "it holds data from another import; not touching it.")
        last_id = src_last.id
        print(f"{table.name}/{region}: resuming after {done}/{total} rows")

    cols = _data_columns(table)
    copied = 0
    started = time.monotonic()
    while True:
        for attempt in range(MAX_RETRIES):
            try:
                with src.connect() as conn:
                    rows = conn.execute(
                        select(table.c.id, *cols)
                        .where(table.c.region == region, table.c.id > last_id)
                        .order_by(table.c.id)
                        .limit(batch_size)
                    ).all()
                if rows:
                    with dst.begin() as conn:
                        conn.execute(table.insert(), [{c.name: getattr(r, c.name) for c in cols} for r in rows])
                break
            except OperationalError as exc:
                # A failed insert transaction rolls back whole, so retrying the
                # same batch can't duplicate rows.
                if attempt == MAX_RETRIES - 1:
                    raise
                print(f"  connection error ({exc.orig}); retrying in {2 ** attempt}s")
                time.sleep(2 ** attempt)
        if not rows:
            break
        last_id = rows[-1].id
        copied += len(rows)
        if copied % (batch_size * 20) < batch_size or done + copied == total:
            rate = copied / max(time.monotonic() - started, 1e-6)
            print(f"  {table.name}/{region}: {done + copied}/{total} ({rate:.0f} rows/s)")
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-url", required=True)
    parser.add_argument("--to-url", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--tables", nargs="+", choices=sorted(TABLES), default=sorted(TABLES))
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    if args.from_url == args.to_url:
        sys.exit("--from-url and --to-url are the same database")
    src = create_engine(_normalize_db_url(args.from_url), pool_pre_ping=True)
    dst = create_engine(_normalize_db_url(args.to_url), pool_pre_ping=True)
    print(f"copying {args.region} from {src.url.host} to {dst.url.host}")
    for name in args.tables:
        copy_table(src, dst, TABLES[name], args.region, args.batch_size)
        print(f"{name}/{args.region}: source {_count(src, TABLES[name], args.region)}, "
              f"destination {_count(dst, TABLES[name], args.region)}")


if __name__ == "__main__":
    main()
