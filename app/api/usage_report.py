from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.usage_report import ReportWarning, UsageReportPayload, UsageReportRow
from app.services.imports import parse_csv_rows
from app.services.report_sessions import (
    ReportSession,
    ReportSessionSummary,
    create_report_session,
    delete_report_session_data,
    get_report_session,
    preview_report_session,
    submit_report_session,
)

router = APIRouter(prefix="/api/usage-report", tags=["usage-report"])


class CreateReportSessionRequest(BaseModel):
    reporter_label: str | None = None


class PreviewReportRequest(BaseModel):
    rows: list[UsageReportRow] = Field(min_length=1)
    warnings: list[ReportWarning] = Field(default_factory=list)


class PreviewCsvRequest(BaseModel):
    csv_text: str = Field(min_length=1)


@router.post("/sessions", response_model=ReportSession, status_code=201)
def create_usage_report_session(
    payload: CreateReportSessionRequest,
    db: Session = Depends(get_db),
) -> ReportSession:
    return create_report_session(db, reporter_label=payload.reporter_label)


@router.get("/sessions/{session_id}", response_model=ReportSessionSummary)
def get_usage_report_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    session = _get_session_or_404(db, session_id)
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


@router.post("/sessions/{session_id}/preview", response_model=ReportSessionSummary)
def preview_usage_report_session(
    session_id: str,
    payload: PreviewReportRequest,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    session = _get_session_or_404(db, session_id)
    return preview_report_session(db, session, rows=payload.rows, warnings=payload.warnings)


@router.post("/sessions/{session_id}/preview/csv", response_model=ReportSessionSummary)
def preview_usage_report_session_csv(
    session_id: str,
    payload: PreviewCsvRequest,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    session = _get_session_or_404(db, session_id)
    rows = parse_csv_rows(payload.csv_text)
    warning = ReportWarning(code="csv_import", message="Rows were imported from CSV.")
    return preview_report_session(db, session, rows=rows, warnings=[warning])


@router.post("/sessions/{session_id}/submit", response_model=ReportSessionSummary)
def submit_usage_report_session(
    session_id: str,
    payload: UsageReportPayload,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    session = _get_session_or_404(db, session_id)
    if payload.report_session_id != session.id:
        raise HTTPException(status_code=400, detail="report_session_id does not match session")
    if session.status != "previewed":
        raise HTTPException(status_code=409, detail="report preview is required before submit")
    return submit_report_session(db, session, payload)


@router.delete("/sessions/{session_id}", response_model=ReportSessionSummary)
def delete_usage_report_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> ReportSessionSummary:
    session = _get_session_or_404(db, session_id)
    return delete_report_session_data(db, session)


def _get_session_or_404(db: Session, session_id: str) -> ReportSession:
    session = get_report_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="report session not found")
    return session
