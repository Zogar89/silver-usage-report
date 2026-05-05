from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from tests.conftest import signed_post


def _preview(client: TestClient, session: dict[str, object], rows: list[dict[str, object]], warnings=None):
    return signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/preview",
        str(session["private_token"]),
        {"rows": rows, "warnings": warnings or []},
    )


def _submit(client: TestClient, session: dict[str, object], rows: list[dict[str, object]], warnings=None):
    return signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/submit",
        str(session["private_token"]),
        {
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": rows,
            "warnings": warnings or [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )


def test_admin_review_requires_token_when_configured():
    settings = get_settings()
    original_token = settings.admin_token
    settings.admin_token = "test-admin-token"
    try:
        client = TestClient(app)

        denied = client.get("/admin/reports")
        allowed = client.get("/admin/reports", headers={"x-admin-token": "test-admin-token"})

        assert denied.status_code == 401
        assert allowed.status_code == 200
    finally:
        settings.admin_token = original_token


def test_admin_login_sets_cookie_and_allows_browser_access():
    settings = get_settings()
    original_token = settings.admin_token
    settings.admin_token = "test-admin-token"
    try:
        client = TestClient(app)

        login_page = client.get("/admin")
        denied = client.get("/admin/reports")
        logged_in = client.post(
            "/admin/login",
            content="admin_token=test-admin-token",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        reports = client.get("/admin/reports")

        assert login_page.status_code == 200
        assert "Entrar al panel" in login_page.text
        assert denied.status_code == 401
        assert logged_in.status_code == 200
        assert "Revision admin" in logged_in.text
        assert reports.status_code == 200
        assert "Lista de candidatos/reportes" in reports.text
    finally:
        settings.admin_token = original_token


def test_admin_review_requires_token_in_production_even_when_unset():
    settings = get_settings()
    original_token = settings.admin_token
    original_environment = settings.environment
    settings.admin_token = None
    settings.environment = "production"
    try:
        client = TestClient(app)

        response = client.get("/admin/reports")

        assert response.status_code == 503
        assert response.json()["detail"] == "ADMIN_TOKEN must be configured in production"
    finally:
        settings.admin_token = original_token
        settings.environment = original_environment


def test_admin_review_lists_submitted_report_totals():
    client = TestClient(app)
    session = client.post(
        "/api/usage-report/sessions",
        json={
            "reporter_label": "Gabriel",
            "reporter_email": "gabriel@silver.dev",
            "github_handle": "gabriel-silver",
            "candidate_ref": "cand_123",
            "campaign_ref": "open-call-2026",
        },
    ).json()
    row = {
        "provider": "openai",
        "tool": "codex",
        "source": "codex_local_telemetry",
        "period_start": "2026-05-01T00:00:00Z",
        "period_end": "2026-05-02T00:00:00Z",
        "period_width": "1d",
        "model": "gpt-5.5",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_source": "unknown",
        "confidence": "medium",
    }
    _preview(client, session, [row])
    _submit(client, session, [row])

    response = client.get("/admin/reports")

    assert response.status_code == 200
    assert "Revision admin" in response.text
    assert session["public_code"] in response.text
    assert "enviado" in response.text
    assert "150" in response.text
    assert "$0.00" in response.text
    assert "cand_123" in response.text
    assert "gabriel@silver.dev" in response.text

    detail = client.get(f"/admin/reports/{session['id']}")

    assert detail.status_code == 200
    assert "Detalle del reporte" in detail.text
    assert "gabriel-silver" in detail.text
    assert "open-call-2026" in detail.text
    assert "codex_local_telemetry" in detail.text
    assert "Costo estimado" in detail.text
    assert "03 may 2026, 21:01 Argentina" in detail.text


def test_admin_dashboard_shows_collection_progress_by_status():
    client = TestClient(app)
    draft = client.post(
        "/api/usage-report/sessions",
        json={"reporter_label": "Draft user", "candidate_ref": "cand_draft"},
    ).json()
    previewed = client.post(
        "/api/usage-report/sessions",
        json={"reporter_label": "Preview user", "candidate_ref": "cand_preview"},
    ).json()
    submitted = client.post(
        "/api/usage-report/sessions",
        json={"reporter_label": "Submitted user", "candidate_ref": "cand_submitted"},
    ).json()
    row = {
        "provider": "openai",
        "tool": "codex",
        "source": "codex_local_telemetry",
        "period_start": "2026-05-01T00:00:00Z",
        "period_end": "2026-05-02T00:00:00Z",
        "period_width": "1d",
        "request_count": 4,
        "input_tokens": 420,
        "output_tokens": 80,
        "cost_source": "estimated",
        "confidence": "medium",
    }
    _preview(client, previewed, [row])
    _preview(client, submitted, [row])
    _submit(client, submitted, [row], warnings=[{"code": "partial_local_data", "message": "Periodo local parcial."}])

    response = client.get("/admin/reports")

    assert response.status_code == 200
    assert "Reportes activos" in response.text
    assert "Con uso cargado" in response.text
    assert "Enviados" in response.text
    assert "Reportes recientes" in response.text
    assert draft["public_code"] in response.text
    assert previewed["public_code"] in response.text
    assert submitted["public_code"] in response.text
    assert "cand_draft" in response.text
    assert "cand_preview" in response.text
    assert "cand_submitted" in response.text
    assert "500" in response.text
    assert "Las metricas de uso estan dentro del detalle" in response.text


def test_admin_reports_paginates_and_searches_live_results():
    client = TestClient(app)
    sessions = []
    for index in range(7):
        sessions.append(
            client.post(
                "/api/usage-report/sessions",
                json={
                    "reporter_label": f"Dev {index}",
                    "reporter_email": f"dev{index}@silver.dev",
                    "github_handle": f"dev-{index}",
                    "candidate_ref": f"cand_page_{index}",
                },
            ).json()
        )

    first_page = client.get("/admin/reports", params={"per_page": 3})
    second_page = client.get("/admin/reports", params={"per_page": 3, "page": 2})
    search = client.get("/admin/reports", params={"q": "cand_page_2", "per_page": 3}, headers={"HX-Request": "true"})

    assert first_page.status_code == 200
    assert "Pagina 1 de 3" in first_page.text
    assert sessions[-1]["public_code"] in first_page.text
    assert sessions[0]["public_code"] not in first_page.text
    assert second_page.status_code == 200
    assert "Pagina 2 de 3" in second_page.text
    assert search.status_code == 200
    assert "<!doctype html>" not in search.text
    assert "cand_page_2" in search.text
    assert "cand_page_1" not in search.text
    assert "1 reportes encontrados" in search.text


def test_admin_detail_shows_ai_usage_metrics_for_candidate_report():
    client = TestClient(app)
    session = client.post(
        "/api/usage-report/sessions",
        json={"reporter_label": "Ana Dev", "reporter_email": "ana@silver.dev", "candidate_ref": "cand_same"},
    ).json()
    first_row = {
        "provider": "openai",
        "tool": "codex",
        "source": "codex_local_telemetry",
        "period_start": "2026-05-01T00:00:00Z",
        "period_end": "2026-05-02T00:00:00Z",
        "period_width": "1d",
        "model": "gpt-5.3-codex",
        "request_count": 2,
        "input_tokens": 1000000,
        "output_tokens": 250000,
        "reasoning_tokens": 50000,
        "cost_source": "estimated",
        "confidence": "medium",
    }
    second_row = {
        "provider": "openai",
        "tool": "codex",
        "source": "codex_local_telemetry",
        "period_start": "2026-05-02T00:00:00Z",
        "period_end": "2026-05-03T00:00:00Z",
        "period_width": "1d",
        "model": "gpt-5.4",
        "request_count": 3,
        "input_tokens": 2000000,
        "output_tokens": 800000,
        "cached_input_tokens": 500000,
        "cost_source": "estimated",
        "confidence": "medium",
    }
    _preview(client, session, [first_row, second_row])

    response = client.get(f"/admin/reports/{session['id']}")

    assert response.status_code == 200
    assert "Uso de IA del candidato" in response.text
    assert "Ana Dev" in response.text
    assert "cand_same" in response.text
    assert "4.6M tokens totales" in response.text
    assert "Tokens por dia activo" in response.text
    assert "2.3M" in response.text
    assert "3.5M tokens" in response.text
    assert "3M (85.7% del input total)" in response.text
    assert "22.8% de tokens totales" in response.text
    assert "30% del input total" in response.text
    assert "80% del input total" in response.text
    assert "500K (14.3% del input total)" in response.text
    assert "50K (4.8% del output)" in response.text
    assert "gpt-5.3-codex, gpt-5.4" in response.text
    assert "Serie temporal de tokens por dia" in response.text
    assert "Input nuevo" in response.text
    assert "cdn.jsdelivr.net/npm/chart.js" in response.text
    assert "integrity=\"sha384-b0GXujLkk9eYYSmcSfoyZbfyElGAQnDyY0skCHSG6w3JgTMFnz11ggrTAr7seu9f\"" in response.text
    assert "stacked: true" in response.text
    assert '"fresh_input"' in response.text


def test_admin_detail_shows_warnings_and_row_collection_fields():
    client = TestClient(app)
    session = client.post(
        "/api/usage-report/sessions",
        json={"reporter_label": "Gabriel", "candidate_ref": "cand_warning"},
    ).json()
    row = {
        "provider": "openai",
        "tool": "codex",
        "source": "codex_local_telemetry",
        "period_start": "2026-05-01T00:00:00Z",
        "period_end": "2026-05-02T00:00:00Z",
        "period_width": "1d",
        "model": "gpt-5.3-codex",
        "request_count": 7,
        "input_tokens": 100,
        "output_tokens": 50,
        "cached_input_tokens": 12,
        "reasoning_tokens": 8,
        "cost_usd": 0.37,
        "cost_source": "estimated",
        "confidence": "medium",
        "evidence": {"adapter": "codex_local", "adapter_version": "0.1.0", "row_count": 1},
    }
    warning = {"provider": "openai", "tool": "codex", "code": "partial_local_data", "message": "Periodo local parcial."}
    _preview(client, session, [row], warnings=[warning])

    detail = client.get(f"/admin/reports/{session['id']}")

    assert detail.status_code == 200
    assert "Uso por dia" in detail.text
    assert "01 may 2026" in detail.text
    assert "Calidad y origen de datos" in detail.text
    assert "Ver filas tecnicas" in detail.text
    assert "Advertencias" in detail.text
    assert "partial_local_data" in detail.text
    assert "Periodo local parcial." in detail.text
    assert "gpt-5.3-codex" in detail.text
    assert "codex_local_telemetry" in detail.text
    assert "codex_local" in detail.text
    assert "estimated" in detail.text
    assert "0.37" not in detail.text
    assert "0.1.0" in detail.text


def test_admin_detail_shows_collector_diagnostics():
    client = TestClient(app)
    session = client.post(
        "/api/usage-report/sessions",
        json={"reporter_label": "Collector failed", "candidate_ref": "cand_diag"},
    ).json()
    diagnostic = {
        "stage": "lectura de sesiones locales",
        "error_type": "System.Exception",
        "message": "No se encontro %USERPROFILE%\\.codex\\sessions",
        "solution_hint": "Revisar usuario de Windows.",
        "collector_version": "0.5.0-powershell",
        "powershell_version": "5.1",
        "os": "Windows",
        "sessions_dir_status": "missing",
        "rollout_file_count": 0,
        "context": {"days": 90},
    }
    signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/collector-diagnostics",
        str(session["private_token"]),
        diagnostic,
    )

    detail = client.get(f"/admin/reports/{session['id']}")

    assert detail.status_code == 200
    assert "Fallos reportados por el script" in detail.text
    assert "lectura de sesiones locales" in detail.text
    assert "%USERPROFILE%\\.codex\\sessions" in detail.text
    assert "0.5.0-powershell" in detail.text
    assert "missing" in detail.text


def test_admin_can_delete_report_from_panel():
    client = TestClient(app)
    session = client.post(
        "/api/usage-report/sessions",
        json={"reporter_label": "Delete me", "candidate_ref": "cand_delete"},
    ).json()
    row = {
        "provider": "openai",
        "tool": "codex",
        "source": "codex_local_telemetry",
        "period_start": "2026-05-01T00:00:00Z",
        "period_end": "2026-05-02T00:00:00Z",
        "period_width": "1d",
        "model": "gpt-5.5",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_source": "unknown",
        "confidence": "medium",
    }
    _preview(client, session, [row])

    response = client.post(f"/admin/reports/{session['id']}/delete")
    summary = client.get(
        f"/api/usage-report/sessions/{session['id']}",
        params={"token": session["private_token"]},
    ).json()

    assert response.status_code == 200
    assert f"Reporte {session['public_code']} eliminado" in response.text
    assert "eliminado" in response.text
    assert summary["status"] == "deleted"
    assert summary["row_count"] == 0
    assert summary["total_tokens"] == 0


def test_admin_can_edit_candidate_data():
    client = TestClient(app)
    session = client.post(
        "/api/usage-report/sessions",
        json={"reporter_label": "Old name", "candidate_ref": "old_candidate"},
    ).json()

    response = client.post(
        f"/admin/reports/{session['id']}/identity",
        content=(
            "reporter_label=New%20Name&"
            "reporter_email=new%40silver.dev&"
            "github_handle=new-handle&"
            "x_handle=new_x&"
            "candidate_ref=cand_updated&"
            "campaign_ref=may-2026"
        ),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    summary = client.get(
        f"/api/usage-report/sessions/{session['id']}",
        params={"token": session["private_token"]},
    ).json()

    assert response.status_code == 200
    assert "Datos del candidato actualizados" in response.text
    assert "New Name" in response.text
    assert "new@silver.dev" in response.text
    assert "cand_updated" in response.text
    assert summary["reporter_label"] == "New Name"
    assert summary["reporter_email"] == "new@silver.dev"
    assert summary["github_handle"] == "new-handle"
    assert summary["x_handle"] == "new_x"
    assert summary["candidate_ref"] == "cand_updated"
    assert summary["campaign_ref"] == "may-2026"
