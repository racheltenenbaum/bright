"""add feedback table

Revision ID: c1d2e3f4a5b6
Revises: b9d0e1f2a3c4
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b9d0e1f2a3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INT NOT NULL AUTO_INCREMENT,
            user_id INT NOT NULL,
            from_email VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP NULL,
            PRIMARY KEY (id),
            INDEX ix_feedback_user_id (user_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)


def downgrade() -> None:
    op.drop_table("feedback")
