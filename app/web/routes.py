from datetime import UTC, datetime
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.usage_report import ReportWarning, UsageReportPayload, UsageReportRow
from app.services.report_sessions import (
    ReportSession,
    ReportSessionSummary,
    create_report_session,
    delete_report_session_data,
    get_report_session,
    list_report_sessions,
    preview_report_session,
    submit_report_session,
    summarize_report_session,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"title": "Silver Usage Report"},
    )


@router.post("/reports/sessions", response_class=HTMLResponse)
def start_report_session(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = create_report_session(db)
    return _render_session(request, session)


@router.post("/reports/sessions/{session_id}/preview", response_class=HTMLResponse)
async def preview_manual_report_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_session_or_404(db, session_id)
    form = _parse_urlencoded_form(await request.body())
    row = _manual_row_from_form(form)
    warning = ReportWarning(
        code="manual_data",
        message="Manual data is lower confidence.",
    )
    summary = preview_report_session(db, session, rows=[row], warnings=[warning])
    session = _get_session_or_404(db, session_id)
    return _render_session(request, session, summary=summary, banner="Preview ready")


@router.post("/reports/sessions/{session_id}/submit", response_class=HTMLResponse)
def submit_manual_report_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_session_or_404(db, session_id)
    confirmed_at = datetime.now(UTC)
    payload = UsageReportPayload(
        report_session_id=session.id,
        generated_at=confirmed_at,
        rows=session.rows,
        warnings=session.warnings,
        user_confirmation={
            "preview_shown": True,
            "confirmed_at": confirmed_at,
        },
    )
    summary = submit_report_session(db, session, payload)
    session = _get_session_or_404(db, session_id)
    return _render_session(request, session, summary=summary, banner="Report submitted")


@router.post("/reports/sessions/{session_id}/delete", response_class=HTMLResponse)
def delete_manual_report_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_session_or_404(db, session_id)
    summary = delete_report_session_data(db, session)
    session = _get_session_or_404(db, session_id)
    return _render_session(request, session, summary=summary, banner="Report deleted")


@router.get("/admin/reports", response_class=HTMLResponse)
def admin_reports(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    reports = list_report_sessions(db)
    return templates.TemplateResponse(
        request,
        "admin_reports.html",
        {"title": "Admin review", "reports": reports},
    )


def _render_session(
    request: Request,
    session: ReportSession,
    summary: ReportSessionSummary | None = None,
    banner: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "session.html",
        {
            "title": "Report session",
            "session": session,
            "summary": summary or summarize_report_session(session),
            "banner": banner,
        },
    )


def _get_session_or_404(db: Session, session_id: str) -> ReportSession:
    session = get_report_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="report session not found")
    return session


def _parse_urlencoded_form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}


def _manual_row_from_form(form: dict[str, str]) -> UsageReportRow:
    input_tokens = _optional_int(form.get("input_tokens"))
    output_tokens = _optional_int(form.get("output_tokens"))
    total_tokens = (input_tokens or 0) + (output_tokens or 0)
    return UsageReportRow(
        provider=str(form.get("provider") or "other"),
        tool=str(form.get("tool") or "other"),
        source="manual",
        period_start=str(form.get("period_start") or "2026-05-01T00:00:00Z"),
        period_end=str(form.get("period_end") or "2026-05-02T00:00:00Z"),
        period_width="custom",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_source="manual",
        confidence="low",
    )


def _optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
