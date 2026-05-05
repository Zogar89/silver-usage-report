from fastapi.testclient import TestClient

from app.main import app


def _manual_row() -> dict[str, object]:
    return {
        "provider": "openai",
        "tool": "codex",
        "source": "manual",
        "period_start": "2026-05-01T00:00:00Z",
        "period_end": "2026-05-02T00:00:00Z",
        "period_width": "1d",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "cost_source": "manual",
        "confidence": "low",
    }


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
            "github_handle": "gabriel-silver",
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
    assert data["github_handle"] == "gabriel-silver"
    assert data["candidate_ref"] == "cand_123"
    assert data["campaign_ref"] == "open-call-2026"
    assert data["status"] == "draft"


def test_get_report_session_api_returns_private_session_summary_without_token():
    client = TestClient(app)
    session = _create_session(client)

    response = client.get(f"/api/usage-report/sessions/{session['id']}")

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


def test_preview_report_rows_updates_session_status_and_totals():
    client = TestClient(app)
    session = _create_session(client)

    response = client.post(
        f"/api/usage-report/sessions/{session['id']}/preview",
        json={
            "rows": [_manual_row()],
            "warnings": [{"code": "manual_data", "message": "Manual data is lower confidence."}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "previewed"
    assert data["row_count"] == 1
    assert data["total_tokens"] == 150
    assert data["rows"][0]["confidence"] == "low"
    assert data["warnings"][0]["code"] == "manual_data"


def test_submit_requires_a_preview_first():
    client = TestClient(app)
    session = _create_session(client)

    response = client.post(
        f"/api/usage-report/sessions/{session['id']}/submit",
        json={
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [_manual_row()],
            "warnings": [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "report preview is required before submit"


def test_submit_after_preview_marks_session_submitted():
    client = TestClient(app)
    session = _create_session(client)
    client.post(
        f"/api/usage-report/sessions/{session['id']}/preview",
        json={"rows": [_manual_row()], "warnings": []},
    )

    response = client.post(
        f"/api/usage-report/sessions/{session['id']}/submit",
        json={
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [_manual_row()],
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
    client.post(
        f"/api/usage-report/sessions/{session['id']}/preview",
        json={"rows": [_manual_row()], "warnings": []},
    )
    client.post(
        f"/api/usage-report/sessions/{session['id']}/submit",
        json={
            "report_session_id": session["id"],
            "generated_at": "2026-05-04T00:00:00Z",
            "rows": [_manual_row()],
            "warnings": [],
            "user_confirmation": {
                "preview_shown": True,
                "confirmed_at": "2026-05-04T00:01:00Z",
            },
        },
    )

    response = client.delete(f"/api/usage-report/sessions/{session['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["row_count"] == 0
    assert data["total_tokens"] == 0
    assert data["rows"] == []


def test_preview_csv_import_updates_session_summary():
    client = TestClient(app)
    session = _create_session(client)

    response = client.post(
        f"/api/usage-report/sessions/{session['id']}/preview/csv",
        json={
            "csv_text": (
                "provider,tool,source,period_start,period_end,period_width,"
                "input_tokens,output_tokens,cost_source,confidence\n"
                "openai,codex,csv,2026-05-01T00:00:00Z,2026-05-02T00:00:00Z,"
                "1d,100,50,manual,medium\n"
            )
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "previewed"
    assert data["row_count"] == 1
    assert data["total_tokens"] == 150
    assert data["rows"][0]["source"] == "csv"
