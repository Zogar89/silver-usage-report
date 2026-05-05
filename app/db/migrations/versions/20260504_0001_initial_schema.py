"""Initial report session schema.

Revision ID: 20260504_0001
Revises:
Create Date: 2026-05-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260504_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_sessions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("public_code", sa.String(length=16), nullable=False),
        sa.Column("private_token_hash", sa.String(length=128), nullable=False),
        sa.Column("reporter_label", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_report_sessions_public_code"), "report_sessions", ["public_code"])

    op.create_table(
        "usage_report_rows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_session_id", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("tool", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_width", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("request_count", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_creation_input_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("cost_source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_session_id"], ["report_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_usage_report_rows_report_session_id"),
        "usage_report_rows",
        ["report_session_id"],
    )

    op.create_table(
        "report_warnings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_session_id", sa.String(length=80), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("tool", sa.String(length=64), nullable=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_session_id"], ["report_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_report_warnings_report_session_id"),
        "report_warnings",
        ["report_session_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_report_warnings_report_session_id"), table_name="report_warnings")
    op.drop_table("report_warnings")
    op.drop_index(op.f("ix_usage_report_rows_report_session_id"), table_name="usage_report_rows")
    op.drop_table("usage_report_rows")
    op.drop_index(op.f("ix_report_sessions_public_code"), table_name="report_sessions")
    op.drop_table("report_sessions")
