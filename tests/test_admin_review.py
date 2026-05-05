from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


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
        assert "Panel de recoleccion" in reports.text
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
        "source": "manual",
        "period_start": "2026-05-01T00:00:00Z",
        "period_end": "2026-05-02T00:00:00Z",
        "period_width": "1d",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_source": "manual",
        "confidence": "low",
    }
    client.post(f"/api/usage-report/sessions/{session['id']}/preview", json={"rows": [row]})
    client.post(
        f"/api/usage-report/sessions/{session['id']}/submit",
        json={
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [row],
            "warnings": [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )

    response = client.get("/admin/reports")

    assert response.status_code == 200
    assert "Revision admin" in response.text
    assert session["public_code"] in response.text
    assert "submitted" in response.text
    assert "150" in response.text
    assert "cand_123" in response.text
    assert "gabriel@silver.dev" in response.text

    detail = client.get(f"/admin/reports/{session['id']}")

    assert detail.status_code == 200
    assert "Detalle del reporte" in detail.text
    assert "gabriel-silver" in detail.text
    assert "open-call-2026" in detail.text
    assert "manual" in detail.text


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
        "input_tokens": 420,
        "output_tokens": 80,
        "cost_source": "estimated",
        "confidence": "medium",
    }
    client.post(f"/api/usage-report/sessions/{previewed['id']}/preview", json={"rows": [row]})
    client.post(f"/api/usage-report/sessions/{submitted['id']}/preview", json={"rows": [row]})
    client.post(
        f"/api/usage-report/sessions/{submitted['id']}/submit",
        json={
            "report_session_id": submitted["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [row],
            "warnings": [{"code": "partial_local_data", "message": "Periodo local parcial."}],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )

    response = client.get("/admin/reports")

    assert response.status_code == 200
    assert "Panel de recoleccion" in response.text
    assert "Reportes en carga" in response.text
    assert "Borradores" in response.text
    assert "Previsualizados" in response.text
    assert "Enviados" in response.text
    assert draft["public_code"] in response.text
    assert previewed["public_code"] in response.text
    assert submitted["public_code"] in response.text
    assert "cand_draft" in response.text
    assert "cand_preview" in response.text
    assert "cand_submitted" in response.text
    assert "500" in response.text


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
    client.post(f"/api/usage-report/sessions/{session['id']}/preview", json={"rows": [row], "warnings": [warning]})

    detail = client.get(f"/admin/reports/{session['id']}")

    assert detail.status_code == 200
    assert "Senales recolectadas" in detail.text
    assert "Advertencias" in detail.text
    assert "partial_local_data" in detail.text
    assert "Periodo local parcial." in detail.text
    assert "gpt-5.3-codex" in detail.text
    assert "codex_local_telemetry" in detail.text
    assert "codex_local" in detail.text
    assert "estimated" in detail.text
    assert "0.37" in detail.text
    assert "0.1.0" in detail.text
