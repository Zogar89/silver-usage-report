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
    get_report_session_for_management,
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
async def start_report_session(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    form = _parse_urlencoded_form(await request.body())
    session = create_report_session(
        db,
        reporter_label=_blank_to_none(form.get("reporter_label")),
        reporter_email=_blank_to_none(form.get("reporter_email")),
        github_handle=_blank_to_none(form.get("github_handle")),
        x_handle=_blank_to_none(form.get("x_handle")),
        candidate_ref=_blank_to_none(form.get("candidate_ref")),
        campaign_ref=_blank_to_none(form.get("campaign_ref")),
    )
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


@router.get("/reports/sessions/{session_id}/status", response_class=HTMLResponse)
def report_session_status(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if not token:
        raise HTTPException(status_code=401, detail="management token required")
    session = get_report_session_for_management(db, session_id, token)
    if session is None:
        raise HTTPException(status_code=401, detail="invalid management token")
    return templates.TemplateResponse(
        request,
        "status.html",
        {
            "title": "Estado del reporte",
            "session": session,
            "summary": summarize_report_session(session),
            "management_token": token,
        },
    )


@router.post("/reports/sessions/{session_id}/delete-managed", response_class=HTMLResponse)
async def delete_managed_report_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    form = _parse_urlencoded_form(await request.body())
    token = form.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="management token required")
    session = get_report_session_for_management(db, session_id, token)
    if session is None:
        raise HTTPException(status_code=401, detail="invalid management token")
    summary = delete_report_session_data(db, session)
    session = _get_session_or_404(db, session_id)
    return templates.TemplateResponse(
        request,
        "status.html",
        {
            "title": "Estado del reporte",
            "session": session,
            "summary": summary,
            "management_token": token,
            "banner": "Reporte eliminado",
        },
    )


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


@router.get("/admin/reports/{session_id}", response_class=HTMLResponse)
def admin_report_detail(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> HTMLResponse:
    _require_admin_token(x_admin_token)
    session = _get_session_or_404(db, session_id)
    return templates.TemplateResponse(
        request,
        "admin_report_detail.html",
        {
            "title": "Detalle del reporte",
            "session": session,
            "summary": summarize_report_session(session),
        },
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
        '--sessions-dir "$env:USERPROFILE\\.codex\\sessions" '
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
            "management_url": _management_url(request, session),
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


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _management_url(request: Request, session: ReportSession) -> str | None:
    if not session.private_token:
        return None
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/reports/sessions/{session.id}/status?token={session.private_token}"
