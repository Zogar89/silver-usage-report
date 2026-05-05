import time
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.db.models import ReportSessionModel
from app.db.session import SessionLocal
from tests.conftest import signed_post


def _codex_row(**overrides) -> dict[str, object]:
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
        "total_tokens": 150,
        "cost_source": "unknown",
        "confidence": "medium",
    }
    row.update(overrides)
    return row


def _create_session(client: TestClient) -> dict[str, object]:
    response = client.post("/api/usage-report/sessions", json={})
    assert response.status_code == 201
    return response.json()


def test_create_report_session_api_returns_session_details():
    client = TestClient(app)

    response = client.post(
        "/api/usage-report/sessions",
        json={
            "reporter_label": "Gabriel",
            "reporter_email": "gabriel@silver.dev",
            "candidate_ref": "cand_123",
            "campaign_ref": "open-call-2026",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("session_")
    assert len(data["public_code"]) == 6
    assert data["private_token"]
    assert data["reporter_label"] == "Gabriel"
    assert data["reporter_email"] == "gabriel@silver.dev"
    assert data["candidate_ref"] == "cand_123"
    assert data["campaign_ref"] == "open-call-2026"
    assert data["status"] == "draft"


def test_create_report_session_rate_limits_to_five_per_candidate():
    client = TestClient(app)
    for index in range(5):
        response = client.post(
            "/api/usage-report/sessions",
            json={"candidate_ref": "cand_limited", "reporter_email": f"limited{index}@silver.dev"},
        )
        assert response.status_code == 201

    rejected = client.post(
        "/api/usage-report/sessions",
        json={"candidate_ref": "cand_limited", "reporter_email": "another@silver.dev"},
    )

    assert rejected.status_code == 429
    assert rejected.json()["detail"] == "maximum report sessions reached for this candidate"


def test_anonymous_report_sessions_do_not_share_candidate_limit():
    client = TestClient(app)

    responses = [client.post("/api/usage-report/sessions", json={}) for _ in range(6)]

    assert [response.status_code for response in responses] == [201, 201, 201, 201, 201, 201]


def test_get_report_session_api_requires_management_token():
    client = TestClient(app)
    session = _create_session(client)

    denied = client.get(f"/api/usage-report/sessions/{session['id']}")
    response = client.get(
        f"/api/usage-report/sessions/{session['id']}",
        params={"token": session["private_token"]},
    )

    assert denied.status_code == 401
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session["id"]
    assert data["public_code"] == session["public_code"]
    assert data["status"] == "draft"
    assert "private_token" not in data


def test_get_private_report_status_requires_management_token():
    client = TestClient(app)
    session = _create_session(client)

    denied = client.get(f"/api/usage-report/sessions/{session['id']}/status")
    allowed = client.get(
        f"/api/usage-report/sessions/{session['id']}/status",
        params={"token": session["private_token"]},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    data = allowed.json()
    assert data["id"] == session["id"]
    assert data["management_url"].endswith(
        f"/reports/sessions/{session['id']}/status?token={session['private_token']}"
    )


def test_mutating_report_session_api_requires_management_token():
    client = TestClient(app)
    session = _create_session(client)

    preview = client.post(f"/api/usage-report/sessions/{session['id']}/preview", json={"rows": [_codex_row()]})
    submit = client.post(
        f"/api/usage-report/sessions/{session['id']}/submit",
        json={
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [_codex_row()],
            "warnings": [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )
    diagnostic = client.post(
        f"/api/usage-report/sessions/{session['id']}/collector-diagnostics",
        json={"stage": "x", "message": "missing"},
    )
    deleted = client.delete(f"/api/usage-report/sessions/{session['id']}")

    assert preview.status_code == 401
    assert submit.status_code == 401
    assert diagnostic.status_code == 401
    assert deleted.status_code == 401


def test_collector_diagnostics_are_recorded_for_failed_script_runs():
    client = TestClient(app)
    session = _create_session(client)

    response = signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/collector-diagnostics",
        session["private_token"],
        {
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
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"

    status = client.get(
        f"/api/usage-report/sessions/{session['id']}/status",
        params={"token": session["private_token"]},
    )

    assert status.status_code == 200
    diagnostic = status.json()["collector_diagnostics"][0]
    assert diagnostic["stage"] == "lectura de sesiones locales"
    assert diagnostic["sessions_dir_status"] == "missing"
    assert diagnostic["rollout_file_count"] == 0


def test_collector_diagnostics_reject_sensitive_context():
    client = TestClient(app)
    session = _create_session(client)

    response = signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/collector-diagnostics",
        session["private_token"],
        {"stage": "x", "message": "missing", "context": {"api_key": "secret"}},
    )

    assert response.status_code == 422


def test_mutating_report_session_api_requires_valid_payload_signature():
    client = TestClient(app)
    session = _create_session(client)

    missing_signature = client.post(
        f"/api/usage-report/sessions/{session['id']}/preview",
        params={"token": session["private_token"]},
        json={"rows": "not parsed before signature"},
    )
    bad_signature = client.post(
        f"/api/usage-report/sessions/{session['id']}/preview",
        params={"token": session["private_token"]},
        json={"rows": [_codex_row()]},
        headers={
            "x-silver-timestamp": str(int(time.time())),
            "x-silver-signature": "bad",
        },
    )

    assert missing_signature.status_code == 401
    assert missing_signature.json()["detail"] == "signed payload required"
    assert bad_signature.status_code == 401
    assert bad_signature.json()["detail"] == "invalid payload signature"


def test_expired_report_session_token_is_rejected():
    client = TestClient(app)
    session = _create_session(client)
    with SessionLocal() as db:
        session_model = db.get(ReportSessionModel, session["id"])
        session_model.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    response = client.get(
        f"/api/usage-report/sessions/{session['id']}",
        params={"token": session["private_token"]},
    )

    assert response.status_code == 401


def test_preview_cannot_reopen_submitted_or_deleted_report():
    client = TestClient(app)
    session = _create_session(client)
    signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/submit",
        session["private_token"],
        {
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [_codex_row()],
            "warnings": [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )

    after_submit = signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/preview",
        session["private_token"],
        {"rows": [_codex_row(total_tokens=42, input_tokens=42, output_tokens=0)], "warnings": []},
    )
    deleted = client.delete(f"/api/usage-report/sessions/{session['id']}", params={"token": session["private_token"]})
    after_delete = signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/preview",
        session["private_token"],
        {"rows": [_codex_row(total_tokens=77, input_tokens=77, output_tokens=0)], "warnings": []},
    )

    assert after_submit.status_code == 409
    assert deleted.status_code == 200
    assert after_delete.status_code == 409


def test_client_supplied_cost_is_recalculated_server_side():
    client = TestClient(app)
    session = _create_session(client)
    forged_row = _codex_row(cost_usd=999999.0, cost_source="provider_actual")

    response = signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/submit",
        session["private_token"],
        {
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [forged_row],
            "warnings": [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["total_cost_usd"] == 0.002
    assert data["rows"][0]["cost_usd"] == 0.002
    assert data["rows"][0]["cost_source"] == "estimated"


def test_collector_diagnostics_reject_sensitive_values():
    client = TestClient(app)
    session = _create_session(client)

    response = signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/collector-diagnostics",
        session["private_token"],
        {"stage": "x", "message": "api_key sk-test-secret", "context": {"days": 90}},
    )

    assert response.status_code == 422


def test_preview_report_rows_updates_session_status_and_totals():
    client = TestClient(app)
    session = _create_session(client)

    response = signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/preview",
        session["private_token"],
        {
            "rows": [_codex_row()],
            "warnings": [{"code": "codex_local_data", "message": "Codex local telemetry."}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "previewed"
    assert data["row_count"] == 1
    assert data["total_tokens"] == 150
    assert data["total_cost_usd"] == 0.002
    assert data["rows"][0]["cost_usd"] == 0.002
    assert data["rows"][0]["cost_source"] == "estimated"
    assert data["rows"][0]["confidence"] == "medium"
    assert data["warnings"][0]["code"] == "codex_local_data"


def test_submit_after_local_preview_marks_session_submitted():
    client = TestClient(app)
    session = _create_session(client)

    response = signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/submit",
        session["private_token"],
        {
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [_codex_row()],
            "warnings": [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "submitted"
    assert data["row_count"] == 1
    assert data["total_tokens"] == 150
    assert data["total_cost_usd"] == 0.002
    assert data["submitted_at"] == "2026-05-04T00:01:00Z"


def test_submit_after_preview_marks_session_submitted():
    client = TestClient(app)
    session = _create_session(client)
    signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/preview",
        session["private_token"],
        {"rows": [_codex_row()], "warnings": []},
    )

    response = signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/submit",
        session["private_token"],
        {
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [_codex_row()],
            "warnings": [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "submitted"
    assert data["row_count"] == 1
    assert data["total_tokens"] == 150
    assert data["submitted_at"] == "2026-05-04T00:01:00Z"


def test_delete_submitted_report_clears_report_rows():
    client = TestClient(app)
    session = _create_session(client)
    signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/preview",
        session["private_token"],
        {"rows": [_codex_row()], "warnings": []},
    )
    signed_post(
        client,
        f"/api/usage-report/sessions/{session['id']}/submit",
        session["private_token"],
        {
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [_codex_row()],
            "warnings": [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )

    response = client.delete(f"/api/usage-report/sessions/{session['id']}", params={"token": session["private_token"]})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["row_count"] == 0
    assert data["total_tokens"] == 0
    assert data["rows"] == []
