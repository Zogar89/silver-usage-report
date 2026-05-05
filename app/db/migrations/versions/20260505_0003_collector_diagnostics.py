"""Add collector diagnostics.

Revision ID: 20260505_0003
Revises: 20260505_0002
Create Date: 2026-05-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260505_0003"
down_revision: str | None = "20260505_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "collector_diagnostics" in inspector.get_table_names():
        return

    op.create_table(
        "collector_diagnostics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_session_id", sa.String(length=80), nullable=False),
        sa.Column("stage", sa.String(length=120), nullable=False),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("solution_hint", sa.Text(), nullable=True),
        sa.Column("collector_version", sa.String(length=80), nullable=True),
        sa.Column("powershell_version", sa.String(length=80), nullable=True),
        sa.Column("os", sa.String(length=255), nullable=True),
        sa.Column("sessions_dir_status", sa.String(length=80), nullable=True),
        sa.Column("rollout_file_count", sa.Integer(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_session_id"], ["report_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_collector_diagnostics_report_session_id"),
        "collector_diagnostics",
        ["report_session_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_collector_diagnostics_report_session_id"), table_name="collector_diagnostics")
    op.drop_table("collector_diagnostics")
