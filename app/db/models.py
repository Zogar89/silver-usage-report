from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ReportSessionModel(Base):
    __tablename__ = "report_sessions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    public_code: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    private_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    reporter_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reporter_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    x_handle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    candidate_ref: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    campaign_ref: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rows: Mapped[list["UsageReportRowModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="UsageReportRowModel.id",
    )
    warnings: Mapped[list["ReportWarningModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ReportWarningModel.id",
    )
    collector_diagnostics: Mapped[list["CollectorDiagnosticModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CollectorDiagnosticModel.id",
    )


class UsageReportRowModel(Base):
    __tablename__ = "usage_report_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_session_id: Mapped[str] = mapped_column(ForeignKey("report_sessions.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_width: Mapped[str] = mapped_column(String(16), nullable=False)
    model_name: Mapped[str | None] = mapped_column("model", String(120), nullable=True)
    request_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_creation_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_source: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[ReportSessionModel] = relationship(back_populates="rows")


class ReportWarningModel(Base):
    __tablename__ = "report_warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_session_id: Mapped[str] = mapped_column(ForeignKey("report_sessions.id"), index=True)
    row_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[ReportSessionModel] = relationship(back_populates="warnings")


class CollectorDiagnosticModel(Base):
    __tablename__ = "collector_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_session_id: Mapped[str] = mapped_column(ForeignKey("report_sessions.id"), index=True)
    stage: Mapped[str] = mapped_column(String(120), nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    solution_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    collector_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    powershell_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    os: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sessions_dir_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rollout_file_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[ReportSessionModel] = relationship(back_populates="collector_diagnostics")
