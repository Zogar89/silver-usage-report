from html import unescape

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
    assert "Codigo de sesion" in html
    assert "Carga manual" in html
    assert "Importar CSV" in html
    assert "Importar JSON" in html
    assert "Previsualizar reporte" in html
    assert "Datos compartidos con Silver" in html


def test_report_session_page_prioritizes_local_agent_cli_import():
    client = TestClient(app)

    response = client.post("/reports/sessions")

    assert response.status_code == 200
    html = response.text
    rendered_text = unescape(html)
    session_id = _session_id_from(html)
    assert "Importacion con agente local" in html
    assert "Comando automatico para Windows" in html
    assert f'irm "http://testserver/reports/sessions/{session_id}/collector.ps1" | iex' in rendered_text
    assert "Descarga el collector y lo ejecuta desde una carpeta temporal." in html
    assert "YOU" not in html
    assert html.index("Importacion con agente local") < html.index("Carga manual")


def test_report_session_collector_script_downloads_and_runs_collector():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)

    script = client.get(f"/reports/sessions/{session_id}/collector.ps1")

    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/plain")
    assert "Invoke-WebRequest" in script.text
    assert "/static/downloads/silver-usage-collector.exe" in script.text
    assert f'--session "{session_id}"' in script.text
    assert '--sessions-dir "$env:USERPROFILE\\.codex\\sessions"' in script.text
    assert "--days 30" in script.text
    assert '--base-url "http://testserver"' in script.text


def test_home_page_uses_spanish_copy_and_language_attribute():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert '<html lang="es">' in html
    assert "Para talento" in html
    assert "Enviar reporte" in html
    assert "metricas agregadas" in html
    assert "Start report" not in html
    assert "For Talent" not in html


def test_report_status_page_requires_private_token_and_shows_management_actions():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)
    token_marker = 'data-private-token="'
    token_start = response.text.index(token_marker) + len(token_marker)
    token_end = response.text.index('"', token_start)
    private_token = response.text[token_start:token_end]

    denied = client.get(f"/reports/sessions/{session_id}/status")
    allowed = client.get(f"/reports/sessions/{session_id}/status", params={"token": private_token})

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert "Estado del reporte" in allowed.text
    assert "Codigo de sesion" in allowed.text
    assert "Eliminar datos del reporte" in allowed.text


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
    assert "Previsualizacion lista" in preview.text
    assert "150" in preview.text
    assert "Confirmar envio" in preview.text

    submitted = client.post(f"/reports/sessions/{session_id}/submit")

    assert submitted.status_code == 200
    assert "Reporte enviado" in submitted.text
    assert "150" in submitted.text

    deleted = client.post(f"/reports/sessions/{session_id}/delete")

    assert deleted.status_code == 200
    assert "Reporte eliminado" in deleted.text
    assert "0 filas retenidas" in deleted.text


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
    assert "Previsualizacion CSV lista" in preview.text
    assert "Filas previsualizadas" in preview.text
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
    assert "Previsualizacion JSON lista" in preview.text
    assert "Filas previsualizadas" in preview.text
    assert "json" in preview.text
    assert "150" in preview.text
