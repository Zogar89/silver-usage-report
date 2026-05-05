from datetime import UTC, datetime
from textwrap import dedent
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.usage_report import UsageReportPayload
from app.services.report_sessions import (
    DEFAULT_REPORTS_PER_PAGE,
    ReportSession,
    ReportSessionLimitError,
    ReportSessionStateError,
    ReportSessionSummary,
    create_report_session,
    delete_report_session_data,
    get_report_session_for_management,
    get_report_session,
    list_report_sessions_page,
    list_report_sessions,
    submit_report_session,
    summarize_report_session,
    update_report_session_identity,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
ADMIN_COOKIE_NAME = "silver_admin_token"
ARGENTINA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"title": "Silver Usage Report"},
    )


@router.post("/reports/sessions")
async def start_report_session(
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = _parse_urlencoded_form(await request.body())
    try:
        session = create_report_session(
            db,
            reporter_label=_blank_to_none(form.get("reporter_label")),
            reporter_email=_blank_to_none(form.get("reporter_email")),
            github_handle=_blank_to_none(form.get("github_handle")),
            x_handle=_blank_to_none(form.get("x_handle")),
            candidate_ref=_blank_to_none(form.get("candidate_ref")),
            campaign_ref=_blank_to_none(form.get("campaign_ref")),
        )
    except ReportSessionLimitError as exc:
        raise HTTPException(status_code=429, detail="maximum report sessions reached for this candidate") from exc
    return RedirectResponse(url=_session_url(request, session), status_code=303)


@router.post("/reports/sessions/open")
async def open_existing_report_session(request: Request) -> RedirectResponse:
    form = _parse_urlencoded_form(await request.body())
    session_id, token = _parse_management_link(form.get("management_url", ""))
    if not session_id or not token:
        raise HTTPException(status_code=400, detail="private report link required")
    return RedirectResponse(url=f"/reports/sessions/{session_id}?token={token}", status_code=303)


@router.get("/reports/sessions/{session_id}", response_class=HTMLResponse)
def report_session_page(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_managed_session_or_401(db, session_id, token)
    if session.status == "submitted":
        return RedirectResponse(url=_session_report_path(session.id, token), status_code=303)
    return _render_session(request, session)


@router.post("/reports/sessions/{session_id}/submit", response_class=HTMLResponse)
def submit_report_session_page(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_managed_session_or_401(db, session_id, token)
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
    try:
        submit_report_session(db, session, payload)
    except ReportSessionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RedirectResponse(url=_session_report_path(session_id, token, {"sent": "1"}), status_code=303)


@router.get("/reports/sessions/{session_id}/report", response_class=HTMLResponse)
def report_session_detail_page(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_managed_session_or_401(db, session_id, token)
    summary = summarize_report_session(session)
    return templates.TemplateResponse(
        request,
        "admin_report_detail.html",
        {
            "title": "Reporte de uso",
            "session": session,
            "summary": summary,
            "usage_metrics": _report_usage_metrics(summary),
            "viewer": "candidate",
            "management_token": token,
            "sent": request.query_params.get("sent") == "1",
        },
    )


@router.post("/reports/sessions/{session_id}/delete", response_class=HTMLResponse)
def delete_report_session_page(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_managed_session_or_401(db, session_id, token)
    summary = delete_report_session_data(db, session)
    session = _get_managed_session_or_401(db, session_id, token)
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
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    session = _get_managed_session_or_401(db, session_id, token)
    if session.status == "submitted":
        return Response(status_code=204, headers={"HX-Redirect": _session_report_path(session.id, token)})
    return templates.TemplateResponse(
        request,
        "_session_preview_panel.html",
        {
            "session": session,
            "summary": summarize_report_session(session),
            "management_token": token,
        },
    )


@router.get("/reports/sessions/{session_id}/report-redirect")
def report_session_redirect_status(
    session_id: str,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> Response:
    session = _get_managed_session_or_401(db, session_id, token)
    headers = {}
    if session.status == "submitted":
        headers["HX-Redirect"] = _session_report_path(session.id, token)
    return Response(status_code=204, headers=headers)


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
def collector_script(
    session_id: str,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> Response:
    session = _get_managed_session_or_401(db, session_id, token)
    base_url = str(request.base_url).rstrip("/")
    script = _collector_powershell_script(session.id, base_url, token or "")
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
    q: str | None = None,
    page: int = 1,
    per_page: int = DEFAULT_REPORTS_PER_PAGE,
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> HTMLResponse:
    _require_admin_token(request, x_admin_token)
    all_reports = list_report_sessions(db)
    report_page = list_report_sessions_page(db, page=page, per_page=per_page, query=q)
    context = {
        "title": "Revision admin",
        "reports": report_page.items,
        "report_page": report_page,
        "dashboard": _admin_dashboard(all_reports),
        "deleted_code": request.query_params.get("deleted"),
    }
    if request.headers.get("hx-request") == "true":
        return templates.TemplateResponse(request, "_admin_reports_results.html", context)
    return templates.TemplateResponse(
        request,
        "admin_reports.html",
        context,
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
    summary = summarize_report_session(session)
    return templates.TemplateResponse(
        request,
        "admin_report_detail.html",
        {
            "title": "Detalle del reporte",
            "session": session,
            "summary": summary,
            "usage_metrics": _report_usage_metrics(summary),
            "saved": request.query_params.get("saved") == "1",
            "viewer": "admin",
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
    submitted_count = sum(1 for report in reports if report.status == "submitted")
    active_reports = [report for report in reports if report.status != "deleted"]
    latest_activity = max(
        (
            report.submitted_at or report.created_at
            for report in active_reports
            if report.submitted_at or report.created_at
        ),
        default=None,
    )
    return {
        "report_count": len(active_reports),
        "reports_with_usage": sum(1 for report in active_reports if report.row_count > 0),
        "submitted_count": submitted_count,
        "pending_count": sum(1 for report in active_reports if report.status in {"draft", "previewed"}),
        "total_cost_usd": round(sum(report.total_cost_usd for report in active_reports), 6),
        "latest_activity": latest_activity,
    }


def _report_usage_metrics(report: ReportSessionSummary) -> dict[str, object]:
    active_day_count = len({day.day for day in report.daily_usage})
    request_count = sum(day.request_count for day in report.daily_usage)
    input_tokens = sum(day.input_tokens for day in report.daily_usage)
    output_tokens = sum(day.output_tokens for day in report.daily_usage)
    cached_input_tokens = sum(day.cached_input_tokens for day in report.daily_usage)
    reasoning_tokens = sum(day.reasoning_tokens for day in report.daily_usage)
    models = sorted({row.model for row in report.rows if row.model})
    token_mix = _token_mix(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=report.total_tokens,
    )
    return {
        "active_day_count": active_day_count,
        "request_count": request_count,
        "total_tokens": report.total_tokens,
        "total_cost_usd": report.total_cost_usd,
        "tokens_per_request": _safe_ratio(report.total_tokens, request_count),
        "tokens_per_active_day": _safe_ratio(report.total_tokens, active_day_count),
        "input_tokens": input_tokens,
        "input_total_tokens": token_mix["input_total_tokens"],
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "reasoning_tokens": reasoning_tokens,
        **token_mix,
        "output_input_percent": _safe_percent(output_tokens, token_mix["input_total_tokens"]),
        "output_fresh_input_percent": _safe_percent(output_tokens, token_mix["fresh_input_tokens"]),
        "input_share": _safe_percent(token_mix["input_total_tokens"], report.total_tokens),
        "output_share": _safe_percent(output_tokens, report.total_tokens),
        "reasoning_share": _safe_percent(reasoning_tokens, output_tokens),
        "cache_share": _safe_percent(cached_input_tokens, token_mix["input_total_tokens"]),
        "fresh_input_share": _safe_percent(token_mix["fresh_input_tokens"], token_mix["input_total_tokens"]),
        "models": models,
        "model_count": len(models),
        "daily_usage": [_daily_usage_metrics(day) for day in report.daily_usage],
        "chartjs": _chartjs_daily_usage_data(report.daily_usage),
        "data_quality": _report_data_quality(report),
    }


def _daily_usage_metrics(day) -> dict[str, object]:
    token_mix = _token_mix(
        input_tokens=day.input_tokens,
        output_tokens=day.output_tokens,
        cached_input_tokens=day.cached_input_tokens,
        reasoning_tokens=day.reasoning_tokens,
        total_tokens=day.total_tokens,
    )
    return {
        "day": day.day,
        "request_count": day.request_count,
        "total_tokens": day.total_tokens,
        "input_tokens": day.input_tokens,
        "input_total_tokens": token_mix["input_total_tokens"],
        "output_tokens": day.output_tokens,
        "cached_input_tokens": day.cached_input_tokens,
        "reasoning_tokens": day.reasoning_tokens,
        **token_mix,
        "tokens_per_request": _safe_ratio(day.total_tokens, day.request_count),
        "input_share": _safe_percent(token_mix["input_total_tokens"], day.total_tokens),
        "output_share": _safe_percent(day.output_tokens, day.total_tokens),
        "cache_share": _safe_percent(day.cached_input_tokens, token_mix["input_total_tokens"]),
        "fresh_input_share": _safe_percent(token_mix["fresh_input_tokens"], token_mix["input_total_tokens"]),
        "reasoning_share": _safe_percent(day.reasoning_tokens, day.output_tokens),
    }


def _report_data_quality(report: ReportSessionSummary) -> dict[str, object]:
    sources = sorted({row.source.value if hasattr(row.source, "value") else str(row.source) for row in report.rows})
    providers = sorted({row.provider.value if hasattr(row.provider, "value") else str(row.provider) for row in report.rows})
    tools = sorted({row.tool.value if hasattr(row.tool, "value") else str(row.tool) for row in report.rows if row.tool})
    confidences = sorted({row.confidence.value if hasattr(row.confidence, "value") else str(row.confidence) for row in report.rows})
    cost_sources = sorted({row.cost_source.value if hasattr(row.cost_source, "value") else str(row.cost_source) for row in report.rows})
    adapters = sorted({row.evidence.adapter for row in report.rows if row.evidence and row.evidence.adapter})
    adapter_versions = sorted(
        {row.evidence.adapter_version for row in report.rows if row.evidence and row.evidence.adapter_version}
    )
    base_row_count = sum(row.evidence.row_count or 0 for row in report.rows if row.evidence)
    period_starts = [row.period_start for row in report.rows]
    period_ends = [row.period_end for row in report.rows]
    return {
        "sources": sources,
        "providers": providers,
        "tools": tools,
        "confidences": confidences,
        "cost_sources": cost_sources,
        "adapters": adapters,
        "adapter_versions": adapter_versions,
        "base_row_count": base_row_count,
        "row_count": report.row_count,
        "warning_count": len(report.warnings),
        "period_start": min(period_starts) if period_starts else None,
        "period_end": max(period_ends) if period_ends else None,
    }


def _chartjs_daily_usage_data(days) -> dict[str, object]:
    rows = [_daily_usage_metrics(day) for day in days]
    return {
        "labels": [row["day"] for row in rows],
        "fresh_input": [row["fresh_input_tokens"] for row in rows],
        "cache": [row["cached_input_tokens"] for row in rows],
        "output": [row["visible_output_tokens"] for row in rows],
        "reasoning": [row["visible_reasoning_tokens"] for row in rows],
        "totals": [row["total_tokens"] for row in rows],
        "requests": [row["request_count"] for row in rows],
    }


def _token_mix(
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int,
    reasoning_tokens: int,
    total_tokens: int | None = None,
) -> dict[str, int]:
    cache_is_included = _input_tokens_include_cache(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
    )
    if cache_is_included:
        billable_cached_tokens = min(cached_input_tokens, input_tokens)
        fresh_input_tokens = max(input_tokens - billable_cached_tokens, 0)
        input_total_tokens = input_tokens
    else:
        billable_cached_tokens = cached_input_tokens
        fresh_input_tokens = input_tokens
        input_total_tokens = input_tokens + cached_input_tokens
    visible_reasoning_tokens = min(reasoning_tokens, output_tokens)
    visible_output_tokens = max(output_tokens - visible_reasoning_tokens, 0)
    chart_total_tokens = fresh_input_tokens + billable_cached_tokens + visible_output_tokens + visible_reasoning_tokens
    return {
        "input_total_tokens": input_total_tokens,
        "fresh_input_tokens": fresh_input_tokens,
        "visible_output_tokens": visible_output_tokens,
        "visible_reasoning_tokens": visible_reasoning_tokens,
        "chart_total_tokens": chart_total_tokens,
    }


def _input_tokens_include_cache(
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    total_tokens: int | None,
) -> bool:
    if total_tokens is None:
        return True
    includes_cache_candidates = (
        input_tokens + output_tokens,
        input_tokens + output_tokens + reasoning_tokens,
    )
    separate_cache_candidates = (
        input_tokens + cached_input_tokens + output_tokens,
        input_tokens + cached_input_tokens + output_tokens + reasoning_tokens,
    )
    includes_delta = min(abs(total_tokens - candidate) for candidate in includes_cache_candidates)
    separate_delta = min(abs(total_tokens - candidate) for candidate in separate_cache_candidates)
    return includes_delta <= separate_delta


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0
    return round(numerator / denominator, 1)


def _safe_percent(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0
    return round((numerator / denominator) * 100, 1)


def _collector_powershell_script(session_id: str, base_url: str, private_token: str) -> str:
    template = r'''
$ErrorActionPreference = "Stop"
$SessionId = "__SESSION_ID__"
$BaseUrl = "__BASE_URL__"
$PrivateToken = "__PRIVATE_TOKEN__"
$Days = 90
$CollectorVersion = "0.5.0-powershell"
$SessionsDir = Join-Path $env:USERPROFILE ".codex\sessions"
$Since = (Get-Date).ToUniversalTime().AddDays(-$Days)
$script:Stage = "inicio"

Write-Host "Silver Usage Collector"
Write-Host "Sesion: $SessionId"
Write-Host "Buscando telemetria en: $SessionsDir"
Write-Host "Periodo: ultimos $Days dias"
Write-Host "Si el collector falla, Silver puede recibir un diagnostico tecnico minimo para mejorar el script."
Write-Host "Ese diagnostico no incluye prompts, respuestas, codigo, logs crudos ni API keys."

function Sanitize-CollectorText($Value) {
  $Text = "$Value"
  if ($env:USERPROFILE) {
    $Text = $Text.Replace($env:USERPROFILE, "%USERPROFILE%")
  }
  return $Text
}

function Get-SilverSignatureHeaders($Body) {
  $Timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds().ToString()
  $Message = "$Timestamp.$Body"
  $KeyBytes = [System.Text.Encoding]::UTF8.GetBytes($PrivateToken)
  $MessageBytes = [System.Text.Encoding]::UTF8.GetBytes($Message)
  $Hmac = [System.Security.Cryptography.HMACSHA256]::new($KeyBytes)
  try {
    $HashBytes = $Hmac.ComputeHash($MessageBytes)
  } finally {
    $Hmac.Dispose()
  }
  $Signature = -join ($HashBytes | ForEach-Object { $_.ToString("x2") })
  return @{
    "X-Silver-Timestamp" = $Timestamp
    "X-Silver-Signature" = $Signature
  }
}

function Send-CollectorDiagnostic($ErrorRecord) {
  try {
    $RolloutCount = $null
    if ($null -ne (Get-Variable -Name Files -Scope Script -ErrorAction SilentlyContinue)) {
      if ($null -ne $script:Files) { $RolloutCount = $script:Files.Count }
    }
    $SessionsDirStatus = $(if (Test-Path $SessionsDir) { "exists" } else { "missing" })
    $Payload = @{
      stage = $script:Stage
      error_type = $ErrorRecord.Exception.GetType().FullName
      message = (Sanitize-CollectorText $ErrorRecord.Exception.Message)
      solution_hint = "Diagnostico automatico del collector. No incluye prompts, respuestas, codigo, logs crudos ni API keys."
      collector_version = $CollectorVersion
      powershell_version = "$($PSVersionTable.PSVersion)"
      os = [System.Environment]::OSVersion.VersionString
      sessions_dir_status = $SessionsDirStatus
      rollout_file_count = $RolloutCount
      context = @{
        days = $Days
        session_id = $SessionId
      }
    } | ConvertTo-Json -Depth 8
    $DiagnosticHeaders = Get-SilverSignatureHeaders $Payload
    Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/usage-report/sessions/$SessionId/collector-diagnostics?token=$([uri]::EscapeDataString($PrivateToken))" -Headers $DiagnosticHeaders -ContentType "application/json" -Body $Payload | Out-Null
    Write-Host "Silver recibio un diagnostico tecnico del fallo para mejorar el collector."
  } catch {
    Write-Host "No se pudo enviar el diagnostico del fallo a Silver."
  }
}

function Show-CollectorError($ErrorRecord) {
  Write-Host ""
  Write-Host "No se pudo completar el reporte." -ForegroundColor Red
  Write-Host "Etapa: $script:Stage"
  Write-Host "Detalle: $($ErrorRecord.Exception.Message)"
  Write-Host ""
  Write-Host "Posibles soluciones:"
  if ($script:Stage -like "lectura*") {
    Write-Host "- Verifica que Codex haya corrido en este usuario de Windows."
    Write-Host "- Revisa que exista esta carpeta: $SessionsDir"
    Write-Host "- Ejecuta PowerShell con el mismo usuario con el que usas Codex."
  } elseif ($script:Stage -like "envio*") {
    Write-Host "- Verifica tu conexion a internet y que puedas abrir $BaseUrl/health"
    Write-Host "- Vuelve a correr el mismo comando desde la pagina del reporte."
    Write-Host "- Si el error es 404 o 401, crea una nueva sesion de reporte y copia el comando nuevo."
  } else {
    Write-Host "- Vuelve a correr el comando una vez mas."
    Write-Host "- Si el problema se repite, envia esta salida a Silver para revisar el collector."
  }
  Write-Host ""
  Write-Host "Se intentara enviar a Silver un diagnostico tecnico minimo del fallo."
  Send-CollectorDiagnostic $ErrorRecord
  Write-Host ""
  Write-Host "No se subieron datos nuevos si el error ocurrio antes del mensaje de envio correcto."
}

trap {
  Show-CollectorError $_
  exit 1
}

function To-Int($Value) {
  if ($null -eq $Value -or "$Value" -eq "") { return $null }
  try { return [int64]$Value } catch { return $null }
}

function Read-Timestamp($Value) {
  try { return ([datetimeoffset]"$Value").UtcDateTime } catch { return (Get-Date).ToUniversalTime() }
}

function Has-TokenUsage($Usage) {
  foreach ($Name in @("input_tokens", "output_tokens", "cached_input_tokens", "cache_creation_input_tokens", "reasoning_tokens", "reasoning_output_tokens", "total_tokens")) {
    if ($null -ne $Usage.$Name -and "$($Usage.$Name)" -ne "") { return $true }
  }
  return $false
}

function Usage-Int($Usage, $Name, $Alias = $null) {
  $Value = To-Int $Usage.$Name
  if ($null -ne $Value) { return $Value }
  if ($Alias) { return (To-Int $Usage.$Alias) }
  return $null
}

function Usage-Total($Usage) {
  $Explicit = Usage-Int $Usage "total_tokens"
  if ($null -ne $Explicit) { return $Explicit }
  $Total = 0
  foreach ($Value in @(
    (Usage-Int $Usage "input_tokens"),
    (Usage-Int $Usage "output_tokens"),
    (Usage-Int $Usage "cached_input_tokens"),
    (Usage-Int $Usage "cache_creation_input_tokens"),
    (Usage-Int $Usage "reasoning_tokens" "reasoning_output_tokens")
  )) {
    if ($null -ne $Value) { $Total += $Value }
  }
  if ($Total -gt 0) { return $Total }
  return $null
}

function To-Float($Value) {
  if ($null -eq $Value -or "$Value" -eq "") { return $null }
  try { return [double]$Value } catch { return $null }
}

function Sum-Field($Items, $Name) {
  $Total = 0
  $Found = $false
  foreach ($Item in $Items) {
    $Value = To-Int $Item.$Name
    if ($null -ne $Value) {
      $Total += $Value
      $Found = $true
    }
  }
  if ($Found) { return $Total }
  return $null
}

function First-Value($Items, $Name) {
  foreach ($Item in $Items) {
    $Value = $Item.$Name
    if ($null -ne $Value -and "$Value" -ne "") { return $Value }
  }
  return $null
}

function Convert-UsageEvent($Parsed) {
  if ($null -eq $Parsed) { return $null }
  $Usage = $Parsed.usage
  $Info = $null
  $RateLimits = $Parsed.rate_limits
  if ($null -eq $Usage -and $Parsed.payload.type -eq "token_count") {
    $Info = $Parsed.payload.info
    $Usage = $Info.total_token_usage
    $RateLimits = $Parsed.payload.rate_limits
  }
  if ($null -eq $Usage -or -not (Has-TokenUsage $Usage)) { return $null }
  return [pscustomobject]@{
    timestamp = (Read-Timestamp $Parsed.timestamp)
    model = $Parsed.model
    provider = $Parsed.model_provider
    model_context_window = (To-Int $Info.model_context_window)
    plan_type = $RateLimits.plan_type
    rate_limit_primary_used_percent = (To-Float $RateLimits.primary.used_percent)
    rate_limit_secondary_used_percent = (To-Float $RateLimits.secondary.used_percent)
    input_tokens = (Usage-Int $Usage "input_tokens")
    output_tokens = (Usage-Int $Usage "output_tokens")
    cached_input_tokens = (Usage-Int $Usage "cached_input_tokens")
    cache_creation_input_tokens = (Usage-Int $Usage "cache_creation_input_tokens")
    reasoning_tokens = (Usage-Int $Usage "reasoning_tokens" "reasoning_output_tokens")
    total_tokens = (Usage-Total $Usage)
  }
}

function Find-SessionMetadata($Lines) {
  $LineArray = @($Lines)
  for ($Index = $LineArray.Count - 1; $Index -ge 0; $Index--) {
    $Line = "$($LineArray[$Index])"
    if ($Line -notlike '*"model"*' -and $Line -notlike '*"model_provider"*') {
      continue
    }
    $Parsed = $null
    try { $Parsed = $Line | ConvertFrom-Json -ErrorAction Stop } catch { $Parsed = $null }
    if ($null -eq $Parsed -or $null -eq $Parsed.payload) { continue }
    $Model = $Parsed.payload.model
    $Provider = $Parsed.payload.model_provider
    $ContextWindow = To-Int $Parsed.payload.model_context_window
    if ($null -ne $Model -or $null -ne $Provider -or $null -ne $ContextWindow) {
      return [pscustomobject]@{
        model = $Model
        provider = $Provider
        model_context_window = $ContextWindow
      }
    }
  }
  return $null
}

function Find-LatestUsage($Lines) {
  $LineArray = @($Lines)
  for ($Index = $LineArray.Count - 1; $Index -ge 0; $Index--) {
    $Line = "$($LineArray[$Index])"
    if ($Line -notlike "*token_count*" -and $Line -notlike "*total_token_usage*" -and $Line -notlike '*"usage"*') {
      continue
    }
    $Parsed = $null
    try { $Parsed = $Line | ConvertFrom-Json -ErrorAction Stop } catch { $Parsed = $null }
    $UsageEvent = Convert-UsageEvent $Parsed
    if ($null -ne $UsageEvent) { return $UsageEvent }
  }
  return $null
}

function Read-TailLines($Path, $ByteCount) {
  $Stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
  try {
    $BytesToRead = [int][Math]::Min($Stream.Length, [int64]$ByteCount)
    if ($BytesToRead -le 0) { return @() }
    $Buffer = New-Object byte[] $BytesToRead
    $Stream.Seek(-$BytesToRead, [System.IO.SeekOrigin]::End) | Out-Null
    $Read = $Stream.Read($Buffer, 0, $BytesToRead)
    $Text = [System.Text.Encoding]::UTF8.GetString($Buffer, 0, $Read)
    return [System.Text.RegularExpressions.Regex]::Split($Text, "\r?\n")
  } finally {
    $Stream.Dispose()
  }
}

$script:Stage = "lectura de sesiones locales"
if (-not (Test-Path $SessionsDir)) {
  throw "No se encontro $SessionsDir. Abri Codex al menos una vez o revisa la instalacion."
}

$script:Files = @(Get-ChildItem -LiteralPath $SessionsDir -Recurse -Filter "rollout-*.jsonl" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTimeUtc -ge $Since.AddDays(-1) } | Sort-Object FullName)
$Files = $script:Files
Write-Host "Archivos rollout encontrados: $($Files.Count)"
if ($Files.Count -eq 0) {
  throw "No se encontraron archivos rollout-*.jsonl en $SessionsDir."
}

$Events = [System.Collections.Generic.List[object]]::new()
$Processed = 0
$FallbackReads = 0
$TailWindows = @(1048576, 4194304, 16777216)
$script:Stage = "lectura de rollouts de Codex"
foreach ($File in $Files) {
  $Processed += 1
  if ($Processed -eq 1 -or ($Processed % 100) -eq 0 -or $Processed -eq $Files.Count) {
    Write-Host "Leyendo archivos: $Processed/$($Files.Count)"
  }
  $Latest = $null
  $Metadata = $null
  foreach ($Window in $TailWindows) {
    $TailLines = Read-TailLines $File.FullName $Window
    if ($null -eq $Latest) {
      $Latest = Find-LatestUsage $TailLines
    }
    if ($null -eq $Metadata) {
      $Metadata = Find-SessionMetadata $TailLines
    }
    if ($null -ne $Latest -and $null -ne $Metadata) { break }
  }
  if ($null -eq $Latest -or $null -eq $Metadata) {
    $FallbackReads += 1
    $CandidateLines = @(Select-String -LiteralPath $File.FullName -SimpleMatch -Pattern '"token_count"', '"total_token_usage"', '"usage"', '"model"', '"model_provider"', '"model_context_window"' -ErrorAction SilentlyContinue | ForEach-Object { $_.Line })
    if ($null -eq $Latest) {
      $Latest = Find-LatestUsage $CandidateLines
    }
    if ($null -eq $Metadata) {
      $Metadata = Find-SessionMetadata $CandidateLines
    }
  }
  if ($null -ne $Latest -and $null -ne $Metadata) {
    if ($null -eq $Latest.model -and $null -ne $Metadata.model) { $Latest.model = $Metadata.model }
    if ($null -eq $Latest.provider -and $null -ne $Metadata.provider) { $Latest.provider = $Metadata.provider }
    if ($null -eq $Latest.model_context_window -and $null -ne $Metadata.model_context_window) { $Latest.model_context_window = $Metadata.model_context_window }
  }
  if ($null -ne $Latest) { $Events.Add($Latest) | Out-Null }
}
if ($FallbackReads -gt 0) {
  Write-Host "Archivos leidos completos por fallback: $FallbackReads"
}

$script:Stage = "preparacion de filas agregadas"
$Events = @($Events | Where-Object { $_.timestamp -ge $Since })
$Rows = @()
$Groups = $Events | Group-Object { "$($_.timestamp.ToString('yyyy-MM-dd'))|$($_.provider)|$($_.model)" }
foreach ($Group in $Groups) {
  $Parts = $Group.Name.Split("|", 3)
  $Day = $Parts[0]
  $Provider = $Parts[1]
  $Model = $Parts[2]
  $DayStart = [datetime]::SpecifyKind(([datetime]::ParseExact($Day, "yyyy-MM-dd", $null)), [DateTimeKind]::Utc)
  $Rows += [pscustomobject]@{
    provider = $(if ($Provider) { $Provider } else { "openai" })
    tool = "codex"
    source = "codex_local_telemetry"
    period_start = $DayStart.ToString("o")
    period_end = $DayStart.AddDays(1).ToString("o")
    period_width = "1d"
    model = $(if ($Model) { $Model } else { $null })
    request_count = $Group.Group.Count
    input_tokens = (Sum-Field $Group.Group "input_tokens")
    output_tokens = (Sum-Field $Group.Group "output_tokens")
    cached_input_tokens = (Sum-Field $Group.Group "cached_input_tokens")
    cache_creation_input_tokens = (Sum-Field $Group.Group "cache_creation_input_tokens")
    reasoning_tokens = (Sum-Field $Group.Group "reasoning_tokens")
    total_tokens = (Sum-Field $Group.Group "total_tokens")
    cost_source = "unknown"
    confidence = "medium"
    evidence = @{
      adapter = "codex_local_telemetry"
      adapter_version = "0.3.0-powershell"
      row_count = $Events.Count
      query_fingerprint = "codex_sessions_daily_model_usage_v1"
      model_context_window = (First-Value $Group.Group "model_context_window")
      plan_type = (First-Value $Group.Group "plan_type")
      rate_limit_primary_used_percent = (First-Value $Group.Group "rate_limit_primary_used_percent")
      rate_limit_secondary_used_percent = (First-Value $Group.Group "rate_limit_secondary_used_percent")
      warnings = @()
    }
  }
}

$TotalTokens = ($Rows | Measure-Object -Property total_tokens -Sum).Sum
$TotalRequests = ($Rows | Measure-Object -Property request_count -Sum).Sum
Write-Host "Rows: $($Rows.Count)"
Write-Host "Requests: $TotalRequests"
Write-Host "Total tokens: $TotalTokens"
if ($Rows.Count -eq 0) {
  throw "No se encontraron datos de Codex en los ultimos $Days dias."
}

$Warnings = @()
Write-Host ""
Write-Host "Previsualizacion local. Nada se envio a Silver todavia."
Write-Host "Esto es lo que se va a enviar si confirmas:"
$Models = @($Rows | Where-Object { $_.model } | Select-Object -ExpandProperty model -Unique)
$Sources = @($Rows | Select-Object -ExpandProperty source -Unique)
[pscustomobject]@{
  filas = $Rows.Count
  requests = $TotalRequests
  total_tokens = $TotalTokens
  periodo = "$($Rows[0].period_start.Substring(0, 10)) a $($Rows[-1].period_start.Substring(0, 10))"
  fuentes = ($Sources -join ", ")
  modelos = $(if ($Models.Count -gt 0) { $Models -join ", " } else { "sin modelo" })
} | Format-List
Write-Host "Primeras filas por volumen de tokens:"
$Rows | Sort-Object total_tokens -Descending | Select-Object -First 8 @{Name="dia";Expression={$_.period_start.Substring(0, 10)}}, model, request_count, input_tokens, output_tokens, total_tokens | Format-Table -AutoSize
Write-Host "Si confirmas, el payload completo queda visible en la pagina donde copiaste este script."

$Answer = Read-Host "Enviar este reporte a Silver? [y/N]"
if ($Answer.ToLower() -notin @("y", "yes", "s", "si")) {
  Write-Host "Envio cancelado."
  exit 2
}

$script:Stage = "preparacion del payload confirmado"
$ConfirmedAt = (Get-Date).ToUniversalTime().ToString("o")
$SubmitPayload = @{
  report_session_id = $SessionId
  generated_at = $ConfirmedAt
  rows = @($Rows)
  warnings = @($Warnings)
  user_confirmation = @{
    preview_shown = $true
    confirmed_at = $ConfirmedAt
  }
} | ConvertTo-Json -Depth 20

$script:Stage = "envio del reporte confirmado"
Write-Host "Enviando reporte confirmado a Silver..."
$SubmitHeaders = Get-SilverSignatureHeaders $SubmitPayload
$SubmitResponse = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/usage-report/sessions/$SessionId/submit?token=$([uri]::EscapeDataString($PrivateToken))" -Headers $SubmitHeaders -ContentType "application/json" -Body $SubmitPayload
Write-Host "Reporte enviado correctamente a Silver."
Write-Host "Estado del servidor: $($SubmitResponse.status)"
Write-Host "Filas recibidas: $($SubmitResponse.row_count)"
Write-Host "Tokens recibidos: $($SubmitResponse.total_tokens)"
Write-Host ""
Write-Host "Ahora podes volver a la pagina donde copiaste este script."
Write-Host "Esa pagina se actualiza sola y va a mostrar los resultados del reporte."
'''
    return (
        dedent(template)
        .strip()
        .replace("__SESSION_ID__", session_id)
        .replace("__BASE_URL__", base_url)
        .replace("__PRIVATE_TOKEN__", private_token)
        + "\n"
    )


def _render_session(
    request: Request,
    session: ReportSession,
    summary: ReportSessionSummary | None = None,
    banner: str | None = None,
) -> HTMLResponse:
    base_url = str(request.base_url).rstrip("/")
    codex_cli_command = (
        f'irm "{base_url}/reports/sessions/{session.id}/collector.ps1?token={session.private_token}" | iex'
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
            "management_token": session.private_token,
        },
    )


@router.post("/admin/reports/{session_id}/delete")
def admin_delete_report(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> RedirectResponse:
    _require_admin_token(request, x_admin_token)
    session = _get_session_or_404(db, session_id)
    public_code = session.public_code
    delete_report_session_data(db, session)
    return RedirectResponse(url=f"/admin/reports?deleted={public_code}", status_code=303)


@router.post("/admin/reports/{session_id}/identity")
async def admin_update_report_identity(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> RedirectResponse:
    _require_admin_token(request, x_admin_token)
    session = _get_session_or_404(db, session_id)
    form = _parse_urlencoded_form(await request.body())
    update_report_session_identity(
        db,
        session,
        reporter_label=_blank_to_none(form.get("reporter_label")),
        reporter_email=_blank_to_none(form.get("reporter_email")),
        github_handle=_blank_to_none(form.get("github_handle")),
        x_handle=_blank_to_none(form.get("x_handle")),
        candidate_ref=_blank_to_none(form.get("candidate_ref")),
        campaign_ref=_blank_to_none(form.get("campaign_ref")),
    )
    return RedirectResponse(url=f"/admin/reports/{session_id}?saved=1#candidate-data", status_code=303)


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


def _parse_urlencoded_form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}


def _parse_management_link(value: str) -> tuple[str | None, str | None]:
    parsed = urlparse(value.strip())
    path_parts = [part for part in parsed.path.split("/") if part]
    token = parse_qs(parsed.query).get("token", [None])[0]
    try:
        reports_index = path_parts.index("reports")
    except ValueError:
        return None, token
    if len(path_parts) <= reports_index + 2 or path_parts[reports_index + 1] != "sessions":
        return None, token
    return path_parts[reports_index + 2], token


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _management_url(request: Request, session: ReportSession) -> str | None:
    if not session.private_token:
        return None
    return _session_url(request, session)


def _session_url(request: Request, session: ReportSession) -> str:
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/reports/sessions/{session.id}?token={session.private_token}"


def _session_report_path(session_id: str, token: str | None, extra_params: dict[str, str] | None = None) -> str:
    params = {}
    if token:
        params["token"] = token
    if extra_params:
        params.update(extra_params)
    query = f"?{urlencode(params)}" if params else ""
    return f"/reports/sessions/{session_id}/report{query}"


_MONTH_NAMES_ES = {
    1: "ene",
    2: "feb",
    3: "mar",
    4: "abr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dic",
}

_STATUS_LABELS = {
    "draft": "borrador",
    "previewed": "previsualizado",
    "submitted": "enviado",
    "deleted": "eliminado",
}


def _format_datetime(value: object, empty: str = "Sin fecha") -> str:
    parsed = _coerce_datetime(value)
    if parsed is None:
        return empty
    parsed = parsed.astimezone(ARGENTINA_TZ)
    month = _MONTH_NAMES_ES[parsed.month]
    return f"{parsed.day:02d} {month} {parsed.year}, {parsed:%H:%M} Argentina"


def _format_date(value: object, empty: str = "Sin fecha") -> str:
    if isinstance(value, str) and len(value) == 10:
        try:
            parsed_date = datetime.fromisoformat(value)
        except ValueError:
            return empty
        month = _MONTH_NAMES_ES[parsed_date.month]
        return f"{parsed_date.day:02d} {month} {parsed_date.year}"
    parsed = _coerce_datetime(value)
    if parsed is None:
        return empty
    parsed = parsed.astimezone(ARGENTINA_TZ)
    month = _MONTH_NAMES_ES[parsed.month]
    return f"{parsed.day:02d} {month} {parsed.year}"


def _format_token_amount(value: object) -> str:
    amount = _coerce_number(value)
    if amount is None:
        return "0"
    absolute = abs(amount)
    if absolute >= 1_000_000:
        return f"{_format_decimal(amount / 1_000_000)}M"
    if absolute >= 1_000:
        return f"{_format_decimal(amount / 1_000)}K"
    return _format_integer(amount)


def _format_count(value: object) -> str:
    amount = _coerce_number(value)
    if amount is None:
        return "0"
    return _format_integer(amount)


def _format_percent(value: object) -> str:
    amount = _coerce_number(value)
    if amount is None:
        return "0%"
    return f"{_format_decimal(amount)}%"


def _format_usd(value: object) -> str:
    amount = _coerce_number(value)
    if amount is None:
        return "Sin costo"
    return f"${amount:,.2f}"


def _status_label(value: str | None) -> str:
    if not value:
        return "sin estado"
    return _STATUS_LABELS.get(value, value)


def _coerce_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _coerce_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_decimal(value: float) -> str:
    formatted = f"{value:,.1f}"
    if formatted.endswith(".0"):
        return formatted[:-2]
    return formatted


def _format_integer(value: float) -> str:
    return f"{int(round(value)):,}"


templates.env.filters["datetime_short"] = _format_datetime
templates.env.filters["date_short"] = _format_date
templates.env.filters["token_amount"] = _format_token_amount
templates.env.filters["number"] = _format_count
templates.env.filters["percent"] = _format_percent
templates.env.filters["usd"] = _format_usd
templates.env.filters["status_label"] = _status_label
