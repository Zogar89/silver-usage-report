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
    session = client.post("/api/usage-report/sessions", json={}).json()
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
