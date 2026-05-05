from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import ReportSessionModel, ReportWarningModel, UsageReportRowModel
from app.schemas.usage_report import ReportWarning, UsageReportPayload, UsageReportRow


class ReportSession(BaseModel):
    id: str
    public_code: str
    private_token: str | None = None
    reporter_label: str | None = None
    status: str = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    submitted_at: datetime | None = None
    rows: list[UsageReportRow] = Field(default_factory=list)
    warnings: list[ReportWarning] = Field(default_factory=list)


class ReportSessionSummary(BaseModel):
    id: str
    public_code: str
    status: str
    row_count: int
    total_tokens: int
    rows: list[UsageReportRow]
    warnings: list[ReportWarning]
    submitted_at: datetime | None = None


def create_report_session(db: Session, reporter_label: str | None = None) -> ReportSession:
    created_at = datetime.now(UTC)
    private_token = token_urlsafe(32)
    session_model = ReportSessionModel(
        id=f"session_{uuid4().hex}",
        public_code=token_urlsafe(8)[:6].upper(),
        private_token_hash=_hash_token(private_token),
        reporter_label=reporter_label,
        status="draft",
        created_at=created_at,
        expires_at=created_at + timedelta(hours=24),
    )
    db.add(session_model)
    db.commit()
    db.refresh(session_model)
    return _to_report_session(session_model, private_token=private_token)


def get_report_session(db: Session, session_id: str) -> ReportSession | None:
    session_model = db.get(ReportSessionModel, session_id)
    if session_model is None:
        return None
    return _to_report_session(session_model)


def list_report_sessions(db: Session) -> list[ReportSessionSummary]:
    session_models = (
        db.query(ReportSessionModel)
        .order_by(ReportSessionModel.created_at.desc())
        .all()
    )
    return [summarize_report_session(_to_report_session(session)) for session in session_models]


def summarize_report_session(session: ReportSession) -> ReportSessionSummary:
    return ReportSessionSummary(
        id=session.id,
        public_code=session.public_code,
        status=session.status,
        row_count=len(session.rows),
        total_tokens=sum(row.total_tokens or 0 for row in session.rows),
        rows=session.rows,
        warnings=session.warnings,
        submitted_at=session.submitted_at,
    )


def preview_report_session(
    db: Session,
    session: ReportSession,
    rows: list[UsageReportRow],
    warnings: list[ReportWarning],
) -> ReportSessionSummary:
    session_model = _require_session_model(db, session.id)
    session_model.rows = [_to_row_model(row) for row in rows]
    session_model.warnings = [_to_warning_model(warning) for warning in warnings]
    session_model.status = "previewed"
    db.commit()
    db.refresh(session_model)
    return summarize_report_session(_to_report_session(session_model))


def submit_report_session(
    db: Session,
    session: ReportSession,
    payload: UsageReportPayload,
) -> ReportSessionSummary:
    session_model = _require_session_model(db, session.id)
    session_model.rows = [_to_row_model(row) for row in payload.rows]
    session_model.warnings = [_to_warning_model(warning) for warning in payload.warnings]
    session_model.submitted_at = payload.user_confirmation.confirmed_at
    session_model.status = "submitted"
    db.commit()
    db.refresh(session_model)
    return summarize_report_session(_to_report_session(session_model))


def delete_report_session_data(db: Session, session: ReportSession) -> ReportSessionSummary:
    session_model = _require_session_model(db, session.id)
    session_model.rows = []
    session_model.warnings = []
    session_model.submitted_at = None
    session_model.status = "deleted"
    db.commit()
    db.refresh(session_model)
    return summarize_report_session(_to_report_session(session_model))


def _hash_token(private_token: str) -> str:
    return sha256(private_token.encode("utf-8")).hexdigest()


def _require_session_model(db: Session, session_id: str) -> ReportSessionModel:
    session_model = db.get(ReportSessionModel, session_id)
    if session_model is None:
        raise ValueError(f"report session not found: {session_id}")
    return session_model


def _to_report_session(
    session_model: ReportSessionModel,
    private_token: str | None = None,
) -> ReportSession:
    return ReportSession(
        id=session_model.id,
        public_code=session_model.public_code,
        private_token=private_token,
        reporter_label=session_model.reporter_label,
        status=session_model.status,
        created_at=_as_utc(session_model.created_at),
        expires_at=_as_utc(session_model.expires_at),
        submitted_at=_as_utc(session_model.submitted_at) if session_model.submitted_at else None,
        rows=[_to_row_schema(row) for row in session_model.rows],
        warnings=[_to_warning_schema(warning) for warning in session_model.warnings],
    )


def _to_row_model(row: UsageReportRow) -> UsageReportRowModel:
    return UsageReportRowModel(
        provider=row.provider.value,
        tool=row.tool.value if row.tool else None,
        source=row.source.value,
        period_start=row.period_start,
        period_end=row.period_end,
        period_width=row.period_width.value,
        model_name=row.model,
        request_count=row.request_count,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        cached_input_tokens=row.cached_input_tokens,
        cache_creation_input_tokens=row.cache_creation_input_tokens,
        reasoning_tokens=row.reasoning_tokens,
        total_tokens=row.total_tokens,
        cost_usd=row.cost_usd,
        cost_source=row.cost_source.value,
        confidence=row.confidence.value,
        evidence_json=row.evidence.model_dump(mode="json") if row.evidence else None,
        created_at=datetime.now(UTC),
    )


def _to_row_schema(row: UsageReportRowModel) -> UsageReportRow:
    return UsageReportRow(
        provider=row.provider,
        tool=row.tool,
        source=row.source,
        period_start=_as_utc(row.period_start),
        period_end=_as_utc(row.period_end),
        period_width=row.period_width,
        model=row.model_name,
        request_count=row.request_count,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        cached_input_tokens=row.cached_input_tokens,
        cache_creation_input_tokens=row.cache_creation_input_tokens,
        reasoning_tokens=row.reasoning_tokens,
        total_tokens=row.total_tokens,
        cost_usd=row.cost_usd,
        cost_source=row.cost_source,
        confidence=row.confidence,
        evidence=row.evidence_json,
    )


def _to_warning_model(warning: ReportWarning) -> ReportWarningModel:
    return ReportWarningModel(
        provider=warning.provider.value if warning.provider else None,
        tool=warning.tool.value if warning.tool else None,
        code=warning.code,
        message=warning.message,
        created_at=datetime.now(UTC),
    )


def _to_warning_schema(warning: ReportWarningModel) -> ReportWarning:
    return ReportWarning(
        provider=warning.provider,
        tool=warning.tool,
        code=warning.code,
        message=warning.message,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
