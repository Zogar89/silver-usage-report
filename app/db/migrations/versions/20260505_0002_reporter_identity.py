"""Add reporter identity and candidate linkage fields.

Revision ID: 20260505_0002
Revises: 20260504_0001
Create Date: 2026-05-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260505_0002"
down_revision: str | None = "20260504_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("report_sessions")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("report_sessions")}

    for name, column_type in (
        ("reporter_email", sa.String(length=255)),
        ("github_handle", sa.String(length=120)),
        ("x_handle", sa.String(length=120)),
        ("candidate_ref", sa.String(length=120)),
        ("campaign_ref", sa.String(length=120)),
    ):
        if name not in existing_columns:
            op.add_column("report_sessions", sa.Column(name, column_type, nullable=True))

    candidate_index = op.f("ix_report_sessions_candidate_ref")
    campaign_index = op.f("ix_report_sessions_campaign_ref")
    if candidate_index not in existing_indexes:
        op.create_index(candidate_index, "report_sessions", ["candidate_ref"])
    if campaign_index not in existing_indexes:
        op.create_index(campaign_index, "report_sessions", ["campaign_ref"])


def downgrade() -> None:
    op.drop_index(op.f("ix_report_sessions_campaign_ref"), table_name="report_sessions")
    op.drop_index(op.f("ix_report_sessions_candidate_ref"), table_name="report_sessions")
    op.drop_column("report_sessions", "campaign_ref")
    op.drop_column("report_sessions", "candidate_ref")
    op.drop_column("report_sessions", "x_handle")
    op.drop_column("report_sessions", "github_handle")
    op.drop_column("report_sessions", "reporter_email")
