from datetime import UTC, datetime
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.usage_report import UsageReportPayload
from app.services.report_sessions import (
    ReportSession,
    ReportSessionSummary,
    create_report_session,
    delete_report_session_data,
    get_report_session_for_management,
    get_report_session,
    list_report_sessions,
    submit_report_session,
    summarize_report_session,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
ADMIN_COOKIE_NAME = "silver_admin_token"


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


@router.post("/reports/sessions/{session_id}/submit", response_class=HTMLResponse)
def submit_report_session_page(
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
def delete_report_session_page(
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


@router.get("/reports/sessions/{session_id}/preview-panel", response_class=HTMLResponse)
def report_session_preview_panel(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_session_or_404(db, session_id)
    return templates.TemplateResponse(
        request,
        "_session_preview_panel.html",
        {
            "session": session,
            "summary": summarize_report_session(session),
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


@router.get("/reports/sessions/{session_id}/collector.ps1")
def collector_script(session_id: str, request: Request, db: Session = Depends(get_db)) -> Response:
    session = _get_session_or_404(db, session_id)
    base_url = str(request.base_url).rstrip("/")
    script = (
        '$ErrorActionPreference = "Stop"\n'
        '$collector = Join-Path $env:TEMP "silver-usage-collector.exe"\n'
        f'Invoke-WebRequest -Uri "{base_url}/static/downloads/silver-usage-collector.exe" -OutFile $collector\n'
        "& $collector submit-codex "
        f'--session "{session.id}" '
        '--sessions-dir "$env:USERPROFILE\\.codex\\sessions" '
        "--days 30 "
        f'--base-url "{base_url}"\n'
    )
    return Response(content=script, media_type="text/plain")


@router.get("/admin", response_class=HTMLResponse)
def admin_login(request: Request) -> HTMLResponse:
    _ensure_admin_configured()
    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {"title": "Entrar al panel"},
    )


@router.post("/admin/login")
async def admin_login_submit(request: Request) -> RedirectResponse:
    form = _parse_urlencoded_form(await request.body())
    token = form.get("admin_token", "")
    _require_admin_token_value(token)
    response = RedirectResponse(url="/admin/reports", status_code=303)
    settings = get_settings()
    if settings.admin_token:
        response.set_cookie(
            ADMIN_COOKIE_NAME,
            token,
            httponly=True,
            samesite="lax",
            secure=settings.environment == "production",
        )
    return response


@router.get("/admin/reports", response_class=HTMLResponse)
def admin_reports(
    request: Request,
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> HTMLResponse:
    _require_admin_token(request, x_admin_token)
    reports = list_report_sessions(db)
    return templates.TemplateResponse(
        request,
        "admin_reports.html",
        {
            "title": "Revision admin",
            "reports": reports,
            "dashboard": _admin_dashboard(reports),
        },
    )


@router.get("/admin/reports/{session_id}", response_class=HTMLResponse)
def admin_report_detail(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> HTMLResponse:
    _require_admin_token(request, x_admin_token)
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


def _ensure_admin_configured() -> None:
    settings = get_settings()
    if settings.environment == "production" and not settings.admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN must be configured in production")


def _require_admin_token(request: Request, x_admin_token: str | None) -> None:
    _ensure_admin_configured()
    settings = get_settings()
    admin_token = settings.admin_token
    request_token = x_admin_token or request.cookies.get(ADMIN_COOKIE_NAME)
    if admin_token and request_token != admin_token:
        raise HTTPException(status_code=401, detail="admin token required")


def _require_admin_token_value(token: str) -> None:
    _ensure_admin_configured()
    admin_token = get_settings().admin_token
    if admin_token and token != admin_token:
        raise HTTPException(status_code=401, detail="admin token required")


def _admin_dashboard(reports: list[ReportSessionSummary]) -> dict[str, object]:
    draft_count = sum(1 for report in reports if report.status == "draft")
    previewed_count = sum(1 for report in reports if report.status == "previewed")
    submitted_count = sum(1 for report in reports if report.status == "submitted")
    deleted_count = sum(1 for report in reports if report.status == "deleted")
    latest_activity = max(
        (report.submitted_at or report.created_at for report in reports if report.submitted_at or report.created_at),
        default=None,
    )
    return {
        "report_count": len(reports),
        "draft_count": draft_count,
        "previewed_count": previewed_count,
        "submitted_count": submitted_count,
        "deleted_count": deleted_count,
        "in_progress_count": draft_count + previewed_count,
        "row_count": sum(report.row_count for report in reports),
        "total_tokens": sum(report.total_tokens for report in reports),
        "warning_count": sum(len(report.warnings) for report in reports),
        "latest_activity": latest_activity,
    }


def _render_session(
    request: Request,
    session: ReportSession,
    summary: ReportSessionSummary | None = None,
    banner: str | None = None,
) -> HTMLResponse:
    base_url = str(request.base_url).rstrip("/")
    codex_cli_command = (
        f'irm "{base_url}/reports/sessions/{session.id}/collector.ps1" | iex'
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
