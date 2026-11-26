"""Add citation_telemetry_json to pr_analyses.

Revision ID: 0002_add_citation_telemetry
Revises: 0001_initial_schema
Create Date: 2026-11-26 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_add_citation_telemetry"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "pr_analyses",
        sa.Column("citation_telemetry_json", JSONVariant, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pr_analyses", "citation_telemetry_json")
