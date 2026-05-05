from fastapi.testclient import TestClient

from app.main import app


def _session_id_from(html: str) -> str:
    marker = 'data-session-id="'
    start = html.index(marker) + len(marker)
    end = html.index('"', start)
    return html[start:end]


def test_report_session_page_shows_manual_entry_preview_surface():
    client = TestClient(app)

    response = client.post("/reports/sessions")

    assert response.status_code == 200
    html = response.text
    assert "Session code" in html
    assert "Manual usage row" in html
    assert "CSV import" in html
    assert "JSON import" in html
    assert "Preview report" in html
    assert "Data shared with Silver" in html


def test_report_session_page_prioritizes_local_agent_cli_import():
    client = TestClient(app)

    response = client.post("/reports/sessions")

    assert response.status_code == 200
    html = response.text
    session_id = _session_id_from(html)
    assert "Local agent import" in html
    assert "python -m cli.main submit-codex" in html
    assert f"--session {session_id}" in html
    assert "--base-url http://testserver" in html
    assert html.index("Local agent import") < html.index("Manual usage row")


def test_manual_web_flow_previews_submits_and_deletes_report():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)

    preview = client.post(
        f"/reports/sessions/{session_id}/preview",
        data={
            "provider": "openai",
            "tool": "codex",
            "period_start": "2026-05-01T00:00:00Z",
            "period_end": "2026-05-02T00:00:00Z",
            "input_tokens": "100",
            "output_tokens": "50",
        },
    )

    assert preview.status_code == 200
    assert "Preview ready" in preview.text
    assert "150" in preview.text
    assert "Confirm submission" in preview.text

    submitted = client.post(f"/reports/sessions/{session_id}/submit")

    assert submitted.status_code == 200
    assert "Report submitted" in submitted.text
    assert "150" in submitted.text

    deleted = client.post(f"/reports/sessions/{session_id}/delete")

    assert deleted.status_code == 200
    assert "Report deleted" in deleted.text
    assert "0 rows retained" in deleted.text


def test_csv_web_flow_previews_rows_in_table():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)

    preview = client.post(
        f"/reports/sessions/{session_id}/preview-csv",
        data={
            "csv_text": (
                "provider,tool,source,period_start,period_end,period_width,input_tokens,output_tokens,cost_source,confidence\n"
                "openai,codex,csv,2026-05-01T00:00:00Z,2026-05-02T00:00:00Z,1d,100,50,manual,medium\n"
            )
        },
    )

    assert preview.status_code == 200
    assert "CSV preview ready" in preview.text
    assert "Preview rows" in preview.text
    assert "codex" in preview.text
    assert "150" in preview.text


def test_json_web_flow_previews_rows_in_table():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)

    preview = client.post(
        f"/reports/sessions/{session_id}/preview-json",
        data={
            "json_text": (
                '{"rows":[{"provider":"openai","tool":"codex","source":"json",'
                '"period_start":"2026-05-01T00:00:00Z","period_end":"2026-05-02T00:00:00Z",'
                '"period_width":"1d","input_tokens":100,"output_tokens":50,'
                '"cost_source":"manual","confidence":"medium"}]}'
            )
        },
    )

    assert preview.status_code == 200
    assert "JSON preview ready" in preview.text
    assert "Preview rows" in preview.text
    assert "json" in preview.text
    assert "150" in preview.text
