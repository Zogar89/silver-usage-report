"""Remove GitHub handle from report sessions.

Revision ID: 20260505_0004
Revises: 20260505_0003
Create Date: 2026-05-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260505_0004"
down_revision: str | None = "20260505_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("report_sessions")}
    if "github_handle" not in columns:
        return
    with op.batch_alter_table("report_sessions") as batch_op:
        batch_op.drop_column("github_handle")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("report_sessions")}
    if "github_handle" in columns:
        return
    with op.batch_alter_table("report_sessions") as batch_op:
        batch_op.add_column(sa.Column("github_handle", sa.String(length=120), nullable=True))
