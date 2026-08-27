"""saved queries for the SQL console

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-12

`folder` is NOT NULL with a `""` default rather than nullable: SQLite counts
every NULL as distinct in a unique index, so unfiled queries would escape the
(folder, name) uniqueness if the top level were spelled NULL.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "saved_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("folder", sa.String(), server_default="", nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("folder", "name", name="uq_saved_query_name_per_folder"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("saved_queries")
