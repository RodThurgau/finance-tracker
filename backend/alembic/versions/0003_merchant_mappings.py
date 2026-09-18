"""merchant name mappings

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-06

A merchant mapping overrides the display name for a `counter_account` value.
The raw value stays on the transaction row; the mapping is resolved at query
time (COALESCE in `stats.py`), so adding or changing a mapping takes effect
immediately with no backfill.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "merchant_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raw_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_name", name="uq_merchant_mapping_raw_name"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("merchant_mappings")
