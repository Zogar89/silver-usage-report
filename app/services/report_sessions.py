from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import (
    CollectorDiagnosticModel,
    ReportSessionModel,
    ReportWarningModel,
    UsageReportRowModel,
)
from app.schemas.usage_report import ReportWarning, UsageReportPayload, UsageReportRow
from app.services.openai_pricing import estimate_report_rows_cost

MAX_REPORT_SESSIONS_PER_CANDIDATE = 5
DEFAULT_REPORTS_PER_PAGE = 25
MAX_REPORTS_PER_PAGE = 100


class ReportSessionLimitError(ValueError):
    pass


class CollectorDiagnostic(BaseModel):
    id: int | None = None
    report_session_id: str
    stage: str
    error_type: str | None = None
    message: str
    solution_hint: str | None = None
    collector_version: str | None = None
    powershell_version: str | None = None
    os: str | None = None
    sessions_dir_status: str | None = None
    rollout_file_count: int | None = None
    context: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReportSession(BaseModel):
    id: str
    public_code: str
    private_token: str | None = None
    reporter_label: str | None = None
    reporter_email: str | None = None
    github_handle: str | None = None
    x_handle: str | None = None
    candidate_ref: str | None = None
    campaign_ref: str | None = None
    status: str = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    submitted_at: datetime | None = None
    rows: list[UsageReportRow] = Field(default_factory=list)
    warnings: list[ReportWarning] = Field(default_factory=list)
    collector_diagnostics: list[CollectorDiagnostic] = Field(default_factory=list)


class DailyUsageSummary(BaseModel):
    day: str
    request_count: int
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    total_tokens: int


class ReportSessionSummary(BaseModel):
    id: str
    public_code: str
    reporter_label: str | None = None
    reporter_email: str | None = None
    github_handle: str | None = None
    x_handle: str | None = None
    candidate_ref: str | None = None
    campaign_ref: str | None = None
    status: str
    row_count: int
    total_tokens: int
    total_cost_usd: float
    daily_usage: list[DailyUsageSummary]
    rows: list[UsageReportRow]
    warnings: list[ReportWarning]
    collector_diagnostics: list[CollectorDiagnostic] = Field(default_factory=list)
    created_at: datetime | None = None
    expires_at: datetime | None = None
    submitted_at: datetime | None = None
    management_url: str | None = None


class ReportSessionPage(BaseModel):
    items: list[ReportSessionSummary]
    page: int
    per_page: int
    total: int
    page_count: int
    query: str | None = None


def create_report_session(
    db: Session,
    reporter_label: str | None = None,
    reporter_email: str | None = None,
    github_handle: str | None = None,
    x_handle: str | None = None,
    candidate_ref: str | None = None,
    campaign_ref: str | None = None,
) -> ReportSession:
    reporter_label = _clean_identifier(reporter_label)
    reporter_email = _clean_identifier(reporter_email)
    github_handle = _clean_identifier(github_handle)
    x_handle = _clean_identifier(x_handle)
    candidate_ref = _clean_identifier(candidate_ref)
    campaign_ref = _clean_identifier(campaign_ref)
    _ensure_candidate_session_limit(
        db,
        reporter_label=reporter_label,
        reporter_email=reporter_email,
        github_handle=github_handle,
        x_handle=x_handle,
        candidate_ref=candidate_ref,
    )
    created_at = datetime.now(UTC)
    private_token = token_urlsafe(32)
    session_model = ReportSessionModel(
        id=f"session_{uuid4().hex}",
        public_code=token_urlsafe(8)[:6].upper(),
        private_token_hash=_hash_token(private_token),
        reporter_label=reporter_label,
        reporter_email=reporter_email,
        github_handle=github_handle,
        x_handle=x_handle,
        candidate_ref=candidate_ref,
        campaign_ref=campaign_ref,
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


def get_report_session_for_management(db: Session, session_id: str, private_token: str) -> ReportSession | None:
    session_model = db.get(ReportSessionModel, session_id)
    if session_model is None:
        return None
    if session_model.private_token_hash != _hash_token(private_token):
        return None
    return _to_report_session(session_model, private_token=private_token)


def list_report_sessions(db: Session) -> list[ReportSessionSummary]:
    session_models = (
        db.query(ReportSessionModel)
        .order_by(ReportSessionModel.created_at.desc())
        .all()
    )
    return [summarize_report_session(_to_report_session(session)) for session in session_models]


def list_report_sessions_page(
    db: Session,
    *,
    page: int = 1,
    per_page: int = DEFAULT_REPORTS_PER_PAGE,
    query: str | None = None,
) -> ReportSessionPage:
    page = max(page, 1)
    per_page = min(max(per_page, 1), MAX_REPORTS_PER_PAGE)
    normalized_query = query.strip() if query else None
    report_query = db.query(ReportSessionModel)
    if normalized_query:
        pattern = f"%{normalized_query}%"
        report_query = report_query.filter(
            or_(
                ReportSessionModel.public_code.ilike(pattern),
                ReportSessionModel.candidate_ref.ilike(pattern),
                ReportSessionModel.campaign_ref.ilike(pattern),
                ReportSessionModel.reporter_label.ilike(pattern),
                ReportSessionModel.reporter_email.ilike(pattern),
                ReportSessionModel.github_handle.ilike(pattern),
                ReportSessionModel.x_handle.ilike(pattern),
                ReportSessionModel.status.ilike(pattern),
            )
        )
    total = report_query.count()
    page_count = max((total + per_page - 1) // per_page, 1)
    page = min(page, page_count)
    session_models = (
        report_query.order_by(ReportSessionModel.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return ReportSessionPage(
        items=[summarize_report_session(_to_report_session(session)) for session in session_models],
        page=page,
        per_page=per_page,
        total=total,
        page_count=page_count,
        query=normalized_query,
    )


def summarize_report_session(session: ReportSession) -> ReportSessionSummary:
    return ReportSessionSummary(
        id=session.id,
        public_code=session.public_code,
        reporter_label=session.reporter_label,
        reporter_email=session.reporter_email,
        github_handle=session.github_handle,
        x_handle=session.x_handle,
        candidate_ref=session.candidate_ref,
        campaign_ref=session.campaign_ref,
        status=session.status,
        row_count=len(session.rows),
        total_tokens=sum(row.total_tokens or 0 for row in session.rows),
        total_cost_usd=round(sum(row.cost_usd or 0 for row in session.rows), 6),
        daily_usage=_summarize_daily_usage(session.rows),
        rows=session.rows,
        warnings=session.warnings,
        collector_diagnostics=session.collector_diagnostics,
        created_at=session.created_at,
        expires_at=session.expires_at,
        submitted_at=session.submitted_at,
    )


def preview_report_session(
    db: Session,
    session: ReportSession,
    rows: list[UsageReportRow],
    warnings: list[ReportWarning],
) -> ReportSessionSummary:
    session_model = _require_session_model(db, session.id)
    rows = estimate_report_rows_cost(rows)
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
    rows = estimate_report_rows_cost(payload.rows)
    session_model.rows = [_to_row_model(row) for row in rows]
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


def update_report_session_identity(
    db: Session,
    session: ReportSession,
    reporter_label: str | None = None,
    reporter_email: str | None = None,
    github_handle: str | None = None,
    x_handle: str | None = None,
    candidate_ref: str | None = None,
    campaign_ref: str | None = None,
) -> ReportSession:
    session_model = _require_session_model(db, session.id)
    session_model.reporter_label = reporter_label
    session_model.reporter_email = reporter_email
    session_model.github_handle = github_handle
    session_model.x_handle = x_handle
    session_model.candidate_ref = candidate_ref
    session_model.campaign_ref = campaign_ref
    db.commit()
    db.refresh(session_model)
    return _to_report_session(session_model)


def record_collector_diagnostic(
    db: Session,
    session: ReportSession,
    diagnostic: CollectorDiagnostic,
) -> CollectorDiagnostic:
    diagnostic_model = CollectorDiagnosticModel(
        report_session_id=session.id,
        stage=diagnostic.stage[:120],
        error_type=diagnostic.error_type[:255] if diagnostic.error_type else None,
        message=diagnostic.message[:2000],
        solution_hint=diagnostic.solution_hint[:2000] if diagnostic.solution_hint else None,
        collector_version=diagnostic.collector_version[:80] if diagnostic.collector_version else None,
        powershell_version=diagnostic.powershell_version[:80] if diagnostic.powershell_version else None,
        os=diagnostic.os[:255] if diagnostic.os else None,
        sessions_dir_status=diagnostic.sessions_dir_status[:80] if diagnostic.sessions_dir_status else None,
        rollout_file_count=diagnostic.rollout_file_count,
        context_json=diagnostic.context,
        created_at=datetime.now(UTC),
    )
    db.add(diagnostic_model)
    db.commit()
    db.refresh(diagnostic_model)
    return _to_collector_diagnostic(diagnostic_model)


def _summarize_daily_usage(rows: list[UsageReportRow]) -> list[DailyUsageSummary]:
    by_day: dict[str, dict[str, int]] = {}
    for row in rows:
        day = row.period_start.date().isoformat()
        values = by_day.setdefault(
            day,
            {
                "request_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_input_tokens": 0,
                "reasoning_tokens": 0,
                "total_tokens": 0,
            },
        )
        values["request_count"] += row.request_count or 0
        values["input_tokens"] += row.input_tokens or 0
        values["output_tokens"] += row.output_tokens or 0
        values["cached_input_tokens"] += row.cached_input_tokens or 0
        values["reasoning_tokens"] += row.reasoning_tokens or 0
        values["total_tokens"] += row.total_tokens or 0
    return [DailyUsageSummary(day=day, **values) for day, values in sorted(by_day.items())]


def _ensure_candidate_session_limit(
    db: Session,
    *,
    reporter_label: str | None,
    reporter_email: str | None,
    github_handle: str | None,
    x_handle: str | None,
    candidate_ref: str | None,
) -> None:
    filters = []
    for column, value in (
        (ReportSessionModel.candidate_ref, candidate_ref),
        (ReportSessionModel.github_handle, github_handle),
        (ReportSessionModel.reporter_email, reporter_email),
        (ReportSessionModel.x_handle, x_handle),
        (ReportSessionModel.reporter_label, reporter_label),
    ):
        normalized = _normalized_identifier(value)
        if normalized:
            filters.append(func.lower(column) == normalized)
    if not filters:
        return
    count = db.query(ReportSessionModel).filter(or_(*filters)).count()
    if count >= MAX_REPORT_SESSIONS_PER_CANDIDATE:
        raise ReportSessionLimitError("candidate report session limit reached")


def _normalized_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().lower()
    return stripped or None


def _clean_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


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
        reporter_email=session_model.reporter_email,
        github_handle=session_model.github_handle,
        x_handle=session_model.x_handle,
        candidate_ref=session_model.candidate_ref,
        campaign_ref=session_model.campaign_ref,
        status=session_model.status,
        created_at=_as_utc(session_model.created_at),
        expires_at=_as_utc(session_model.expires_at),
        submitted_at=_as_utc(session_model.submitted_at) if session_model.submitted_at else None,
        rows=[_to_row_schema(row) for row in session_model.rows],
        warnings=[_to_warning_schema(warning) for warning in session_model.warnings],
        collector_diagnostics=[
            _to_collector_diagnostic(diagnostic)
            for diagnostic in session_model.collector_diagnostics
        ],
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


def _to_collector_diagnostic(diagnostic: CollectorDiagnosticModel) -> CollectorDiagnostic:
    return CollectorDiagnostic(
        id=diagnostic.id,
        report_session_id=diagnostic.report_session_id,
        stage=diagnostic.stage,
        error_type=diagnostic.error_type,
        message=diagnostic.message,
        solution_hint=diagnostic.solution_hint,
        collector_version=diagnostic.collector_version,
        powershell_version=diagnostic.powershell_version,
        os=diagnostic.os,
        sessions_dir_status=diagnostic.sessions_dir_status,
        rollout_file_count=diagnostic.rollout_file_count,
        context=diagnostic.context_json or {},
        created_at=_as_utc(diagnostic.created_at),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
