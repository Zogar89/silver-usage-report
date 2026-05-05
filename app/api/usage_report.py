from datetime import UTC, datetime
from hashlib import sha256
import hmac
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.usage_report import ReportWarning, UsageReportPayload, UsageReportRow, reject_sensitive_fields
from app.services.report_sessions import (
    CollectorDiagnostic,
    ReportSession,
    ReportSessionLimitError,
    ReportSessionStateError,
    ReportSessionSummary,
    create_report_session,
    delete_report_session_data,
    get_report_session_for_management,
    get_report_session,
    preview_report_session,
    record_collector_diagnostic,
    submit_report_session,
    summarize_report_session,
)

router = APIRouter(prefix="/api/usage-report", tags=["usage-report"])
SIGNATURE_WINDOW_SECONDS = 300
MAX_SIGNED_BODY_BYTES = 1_000_000
MAX_REPORT_ROWS = 500
MAX_REPORT_WARNINGS = 100


class CreateReportSessionRequest(BaseModel):
    reporter_label: str | None = Field(default=None, max_length=255)
    reporter_email: str | None = Field(default=None, max_length=255)
    github_handle: str | None = Field(default=None, max_length=120)
    x_handle: str | None = Field(default=None, max_length=120)
    candidate_ref: str | None = Field(default=None, max_length=120)
    campaign_ref: str | None = Field(default=None, max_length=120)


class PreviewReportRequest(BaseModel):
    rows: list[UsageReportRow] = Field(min_length=1, max_length=MAX_REPORT_ROWS)
    warnings: list[ReportWarning] = Field(default_factory=list, max_length=MAX_REPORT_WARNINGS)

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive_input(cls, data):
        if isinstance(data, dict):
            reject_sensitive_fields(data)
        return data


class CollectorDiagnosticRequest(BaseModel):
    stage: str = Field(min_length=1, max_length=120)
    error_type: str | None = Field(default=None, max_length=255)
    message: str = Field(min_length=1, max_length=2000)
    solution_hint: str | None = Field(default=None, max_length=2000)
    collector_version: str | None = Field(default=None, max_length=80)
    powershell_version: str | None = Field(default=None, max_length=80)
    os: str | None = Field(default=None, max_length=255)
    sessions_dir_status: str | None = Field(default=None, max_length=80)
    rollout_file_count: int | None = Field(default=None, ge=0)
    context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive_input(cls, data):
        if isinstance(data, dict):
            reject_sensitive_fields(data)
        return data

    @field_validator("context")
    @classmethod
    def validate_context(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = {"days", "session_id"}
        unknown_keys = set(value) - allowed_keys
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            raise ValueError(f"unsupported diagnostic context fields: {names}")
        reject_sensitive_fields(value)
        if len(str(value)) > 1000:
            raise ValueError("diagnostic context is too large")
        return value


class CollectorDiagnosticResponse(BaseModel):
    status: str
    diagnostic_id: int | None


@router.post("/sessions", response_model=ReportSession, status_code=201)
def create_usage_report_session(
    payload: CreateReportSessionRequest,
    db: Session = Depends(get_db),
) -> ReportSession:
    try:
        return create_report_session(
            db,
            reporter_label=payload.reporter_label,
            reporter_email=payload.reporter_email,
            github_handle=payload.github_handle,
            x_handle=payload.x_handle,
            candidate_ref=payload.candidate_ref,
            campaign_ref=payload.campaign_ref,
        )
    except ReportSessionLimitError as exc:
        raise HTTPException(status_code=429, detail="maximum report sessions reached for this candidate") from exc


@router.get("/sessions/{session_id}", response_model=ReportSessionSummary)
def get_usage_report_session(
    session_id: str,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    session = _get_managed_session_or_401(db, session_id, token)
    return summarize_report_session(session)


@router.get("/sessions/{session_id}/status", response_model=ReportSessionSummary)
def get_private_usage_report_status(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    if not token:
        raise HTTPException(status_code=401, detail="management token required")
    session = get_report_session_for_management(db, session_id, token)
    if session is None:
        raise HTTPException(status_code=401, detail="invalid management token")
    summary = summarize_report_session(session)
    summary.management_url = _management_url(request, session.id, token)
    return summary


@router.post("/sessions/{session_id}/preview", response_model=ReportSessionSummary)
async def preview_usage_report_session(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    session = _get_managed_session_or_401(db, session_id, token)
    body = await _require_signed_body(request, token)
    payload = _parse_signed_payload(PreviewReportRequest, body)
    try:
        return preview_report_session(db, session, rows=payload.rows, warnings=payload.warnings)
    except ReportSessionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/submit", response_model=ReportSessionSummary)
async def submit_usage_report_session(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    session = _get_managed_session_or_401(db, session_id, token)
    body = await _require_signed_body(request, token)
    payload = _parse_signed_payload(UsageReportPayload, body)
    if payload.report_session_id != session.id:
        raise HTTPException(status_code=400, detail="report_session_id does not match session")
    try:
        return submit_report_session(db, session, payload)
    except ReportSessionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/collector-diagnostics", response_model=CollectorDiagnosticResponse)
async def create_collector_diagnostic(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> CollectorDiagnosticResponse:
    session = _get_managed_session_or_401(db, session_id, token)
    body = await _require_signed_body(request, token)
    payload = _parse_signed_payload(CollectorDiagnosticRequest, body)
    diagnostic = record_collector_diagnostic(
        db,
        session,
        CollectorDiagnostic(report_session_id=session.id, **payload.model_dump()),
    )
    return CollectorDiagnosticResponse(status="recorded", diagnostic_id=diagnostic.id)


@router.delete("/sessions/{session_id}", response_model=ReportSessionSummary)
def delete_usage_report_session(
    session_id: str,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    session = _get_managed_session_or_401(db, session_id, token)
    return delete_report_session_data(db, session)


def _get_session_or_404(db: Session, session_id: str) -> ReportSession:
    session = get_report_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="report session not found")
    return session


def _get_managed_session_or_401(db: Session, session_id: str, token: str | None) -> ReportSession:
    if not token:
        raise HTTPException(status_code=401, detail="management token required")
    session = get_report_session_for_management(db, session_id, token)
    if session is None:
        raise HTTPException(status_code=401, detail="invalid management token")
    return session


async def _require_signed_body(request: Request, private_token: str | None) -> bytes:
    if not private_token:
        raise HTTPException(status_code=401, detail="management token required")
    timestamp = request.headers.get("x-silver-timestamp")
    signature = request.headers.get("x-silver-signature")
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="signed payload required")
    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid payload signature timestamp") from exc
    now = int(datetime.now(UTC).timestamp())
    if abs(now - timestamp_value) > SIGNATURE_WINDOW_SECONDS:
        raise HTTPException(status_code=401, detail="payload signature expired")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_SIGNED_BODY_BYTES:
                raise HTTPException(status_code=413, detail="payload too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid content length") from None
    body = await request.body()
    if len(body) > MAX_SIGNED_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")
    expected = _body_signature(private_token, timestamp, body)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="invalid payload signature")
    return body


def _parse_signed_payload(model_type, body: bytes):
    try:
        return model_type.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False)) from exc


def _body_signature(private_token: str, timestamp: str, body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + body
    return hmac.new(private_token.encode("utf-8"), message, sha256).hexdigest()


def _management_url(request: Request, session_id: str, token: str) -> str:
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/reports/sessions/{session_id}/status?token={token}"
