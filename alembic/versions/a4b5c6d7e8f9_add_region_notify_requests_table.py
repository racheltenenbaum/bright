"""add region_notify_requests table

Revision ID: a4b5c6d7e8f9
Revises: e6f7a8b9c0d1
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS region_notify_requests (
            id INT NOT NULL AUTO_INCREMENT,
            user_id INT NOT NULL,
            email VARCHAR(255) NOT NULL,
            lat FLOAT NOT NULL,
            lng FLOAT NOT NULL,
            created_at DATETIME NULL,
            PRIMARY KEY (id),
            CONSTRAINT fk_region_notify_requests_user_id FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)


def downgrade() -> None:
    op.drop_table("region_notify_requests")
