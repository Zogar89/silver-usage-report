import json
from datetime import UTC, datetime
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.usage_report import ReportWarning, UsageReportPayload, UsageReportRow
from app.services.imports import parse_csv_rows, parse_json_rows
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
        message="Los datos manuales tienen menor confianza.",
    )
    summary = preview_report_session(db, session, rows=[row], warnings=[warning])
    session = _get_session_or_404(db, session_id)
    return _render_session(request, session, summary=summary, banner="Previsualizacion lista")


@router.post("/reports/sessions/{session_id}/preview-csv", response_class=HTMLResponse)
async def preview_csv_report_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_session_or_404(db, session_id)
    form = _parse_urlencoded_form(await request.body())
    rows = parse_csv_rows(form.get("csv_text", ""))
    warning = ReportWarning(code="csv_import", message="Las filas fueron importadas desde CSV.")
    summary = preview_report_session(db, session, rows=rows, warnings=[warning])
    session = _get_session_or_404(db, session_id)
    return _render_session(request, session, summary=summary, banner="Previsualizacion CSV lista")


@router.post("/reports/sessions/{session_id}/preview-json", response_class=HTMLResponse)
async def preview_json_report_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_session_or_404(db, session_id)
    form = _parse_urlencoded_form(await request.body())
    rows = parse_json_rows(json.loads(form.get("json_text", "{}")))
    warning = ReportWarning(code="json_import", message="Las filas fueron importadas desde JSON.")
    summary = preview_report_session(db, session, rows=rows, warnings=[warning])
    session = _get_session_or_404(db, session_id)
    return _render_session(request, session, summary=summary, banner="Previsualizacion JSON lista")


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
    return _render_session(request, session, summary=summary, banner="Reporte enviado")


@router.post("/reports/sessions/{session_id}/delete", response_class=HTMLResponse)
def delete_manual_report_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_session_or_404(db, session_id)
    summary = delete_report_session_data(db, session)
    session = _get_session_or_404(db, session_id)
    return _render_session(request, session, summary=summary, banner="Reporte eliminado")


@router.get("/admin/reports", response_class=HTMLResponse)
def admin_reports(
    request: Request,
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> HTMLResponse:
    _require_admin_token(x_admin_token)
    reports = list_report_sessions(db)
    return templates.TemplateResponse(
        request,
        "admin_reports.html",
        {"title": "Revision admin", "reports": reports},
    )


def _require_admin_token(x_admin_token: str | None) -> None:
    settings = get_settings()
    if settings.environment == "production" and not settings.admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN must be configured in production")
    admin_token = settings.admin_token
    if admin_token and x_admin_token != admin_token:
        raise HTTPException(status_code=401, detail="admin token required")


def _render_session(
    request: Request,
    session: ReportSession,
    summary: ReportSessionSummary | None = None,
    banner: str | None = None,
) -> HTMLResponse:
    base_url = str(request.base_url).rstrip("/")
    codex_cli_command = (
        "python -m cli.main submit-codex "
        f"--session {session.id} "
        '--logs-db "C:\\Users\\YOU\\.codex\\logs_2.sqlite" '
        f"--base-url {base_url}"
    )
    return templates.TemplateResponse(
        request,
        "session.html",
        {
            "title": "Sesion de reporte",
            "session": session,
            "summary": summary or summarize_report_session(session),
            "banner": banner,
            "codex_cli_command": codex_cli_command,
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
