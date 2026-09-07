"""add fulfilled and notified to region_notify_requests

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-07 00:00:00.000001

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col["name"] for col in inspect(bind).get_columns("region_notify_requests")}
    if "fulfilled" not in cols:
        op.execute("ALTER TABLE region_notify_requests ADD COLUMN fulfilled TINYINT(1) NOT NULL DEFAULT 0")
    if "notified" not in cols:
        op.execute("ALTER TABLE region_notify_requests ADD COLUMN notified TINYINT(1) NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.drop_column("region_notify_requests", "notified")
    op.drop_column("region_notify_requests", "fulfilled")
