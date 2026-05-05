from html import unescape

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import signed_post


def _session_id_from(html: str) -> str:
    marker = 'data-session-id="'
    start = html.index(marker) + len(marker)
    end = html.index('"', start)
    return html[start:end]


def _private_token_from(html: str) -> str:
    marker = 'data-private-token="'
    start = html.index(marker) + len(marker)
    end = html.index('"', start)
    return html[start:end]


def _management_url_from(html: str) -> str:
    marker = 'href="http://testserver/reports/sessions/'
    start = html.index(marker) + len('href="')
    end = html.index('"', start)
    return unescape(html[start:end])


def test_start_report_session_redirects_to_stable_private_page():
    client = TestClient(app)

    response = client.post("/reports/sessions", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("http://testserver/reports/sessions/session_")
    assert "?token=" in response.headers["location"]


def test_report_session_page_shows_collector_script_without_web_preview():
    client = TestClient(app)

    response = client.post("/reports/sessions")

    assert response.status_code == 200
    html = response.text
    assert "Codigo de sesion" in html
    assert "Collector local de Codex" in html
    assert "Datos compartidos con Silver" not in html
    assert "Filas previsualizadas" not in html
    assert "report-session-flow" not in html
    assert "two-column" not in html
    assert f'/reports/sessions/{_session_id_from(html)}/report-redirect?token={_private_token_from(html)}' in html
    assert "preview-panel" not in html
    assert 'hx-trigger="every 3s"' in html
    assert 'hx-swap="none"' in html
    assert "silverUsageReports" in html
    assert "Guardamos este acceso en este navegador" in html
def test_report_session_page_prioritizes_local_agent_cli_import():
    client = TestClient(app)

    response = client.post("/reports/sessions")

    assert response.status_code == 200
    html = response.text
    rendered_text = unescape(html)
    session_id = _session_id_from(html)
    assert "Collector local de Codex" in html
    assert "Comando PowerShell" in html
    assert "Copiar comando" in html
    assert "Esperando recepcion de datos..." in html
    assert "data-waiting-data hidden" in html
    assert f'irm "http://testserver/reports/sessions/{session_id}/collector.ps1?token=' in rendered_text
    assert "no descarga .exe" in html
    assert "ultimos 90 dias" in html
    assert "YOU" not in html


def test_report_session_private_page_can_be_reopened_with_token():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)
    private_token = _private_token_from(response.text)

    denied = client.get(f"/reports/sessions/{session_id}")
    reopened = client.get(f"/reports/sessions/{session_id}", params={"token": private_token})

    assert denied.status_code == 401
    assert reopened.status_code == 200
    assert session_id in reopened.text
    assert "Collector local de Codex" in reopened.text


def test_submitted_report_session_redirects_private_page_to_report_detail():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)
    private_token = _private_token_from(response.text)
    signed_post(
        client,
        f"/api/usage-report/sessions/{session_id}/submit",
        private_token,
        {
            "report_session_id": session_id,
            "generated_at": "2026-05-01T12:00:00Z",
            "rows": [
                {
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
            ],
            "user_confirmation": {"preview_shown": True, "confirmed_at": "2026-05-01T12:00:00Z"},
        },
    )

    denied = client.get(f"/reports/sessions/{session_id}/report")
    redirected = client.get(f"/reports/sessions/{session_id}", params={"token": private_token}, follow_redirects=False)
    detail = client.get(f"/reports/sessions/{session_id}/report", params={"token": private_token})

    assert denied.status_code == 401
    assert redirected.status_code == 303
    assert redirected.headers["location"] == f"/reports/sessions/{session_id}/report?token={private_token}"
    assert detail.status_code == 200
    assert "Tu reporte de uso de IA" in detail.text
    assert "Uso de IA del candidato" in detail.text
    assert "Serie temporal de tokens por dia" in detail.text
    assert "gpt-5.5" in detail.text
    assert "Confianza" not in detail.text
    assert "Datos del candidato" not in detail.text
    assert "Borrar reporte" in detail.text
    assert f"/reports/sessions/{session_id}/delete?token={private_token}" in detail.text


def test_report_session_redirect_status_moves_candidate_after_submit():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)
    private_token = _private_token_from(response.text)

    waiting = client.get(f"/reports/sessions/{session_id}/report-redirect", params={"token": private_token})
    assert waiting.status_code == 204
    assert "hx-redirect" not in waiting.headers

    signed_post(
        client,
        f"/api/usage-report/sessions/{session_id}/submit",
        private_token,
        {
            "report_session_id": session_id,
            "generated_at": "2026-05-01T12:00:00Z",
            "rows": [
                {
                    "provider": "openai",
                    "tool": "codex",
                    "source": "codex_local_telemetry",
                    "period_start": "2026-05-01T00:00:00Z",
                    "period_end": "2026-05-02T00:00:00Z",
                    "period_width": "1d",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cost_source": "unknown",
                    "confidence": "medium",
                }
            ],
            "user_confirmation": {"preview_shown": True, "confirmed_at": "2026-05-01T12:00:00Z"},
        },
    )

    ready = client.get(f"/reports/sessions/{session_id}/report-redirect", params={"token": private_token})

    assert ready.status_code == 204
    assert ready.headers["hx-redirect"] == f"/reports/sessions/{session_id}/report?token={private_token}"


def test_report_session_collector_script_downloads_and_runs_collector():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)
    private_token = _private_token_from(response.text)

    denied = client.get(f"/reports/sessions/{session_id}/collector.ps1")
    script = client.get(f"/reports/sessions/{session_id}/collector.ps1", params={"token": private_token})

    assert denied.status_code == 401
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/plain")
    assert "Invoke-WebRequest" not in script.text
    assert "silver-usage-collector.exe" not in script.text
    assert f'$SessionId = "{session_id}"' in script.text
    assert f'$PrivateToken = "{private_token}"' in script.text
    assert '$BaseUrl = "http://testserver"' in script.text
    assert "$Days = 90" in script.text
    assert 'Write-Host "Silver Usage Collector"' in script.text
    assert 'Write-Host "Archivos rollout encontrados: $($Files.Count)"' in script.text
    assert 'Write-Host "Leyendo archivos: $Processed/$($Files.Count)"' in script.text
    assert "function Read-TailLines" in script.text
    assert "function Find-SessionMetadata" in script.text
    assert "$TailWindows = @(1048576, 4194304, 16777216)" in script.text
    assert "'\"model\"', '\"model_provider\"', '\"model_context_window\"'" in script.text
    assert "Archivos leidos completos por fallback" in script.text
    assert 'Write-Host "Previsualizacion local. Nada se envio a Silver todavia."' in script.text
    assert 'Write-Host "Esto es lo que se va a enviar si confirmas:"' in script.text
    assert 'Write-Host "Primeras filas por volumen de tokens:"' in script.text
    assert 'Write-Host "Si confirmas, el payload completo queda visible en la pagina donde copiaste este script."' in script.text
    assert "Format-Table -AutoSize" in script.text
    assert "/api/usage-report/sessions/$SessionId/preview" not in script.text
    assert "function Show-CollectorError" in script.text
    assert "function Send-CollectorDiagnostic" in script.text
    assert "function Get-SilverSignatureHeaders" in script.text
    assert '"X-Silver-Timestamp"' in script.text
    assert '"X-Silver-Signature"' in script.text
    assert "Sanitize-CollectorText" in script.text
    assert "/api/usage-report/sessions/$SessionId/collector-diagnostics" in script.text
    assert "-Headers $DiagnosticHeaders" in script.text
    assert "-Headers $SubmitHeaders" in script.text
    assert "Si el collector falla, Silver puede recibir un diagnostico tecnico minimo" in script.text
    assert 'Write-Host "Posibles soluciones:"' in script.text
    assert "Se intentara enviar a Silver un diagnostico tecnico minimo del fallo." in script.text
    assert 'Write-Host "- Verifica tu conexion a internet y que puedas abrir $BaseUrl/health"' in script.text
    assert 'Write-Host "Enviando reporte confirmado a Silver..."' in script.text
    assert 'Write-Host "Reporte enviado correctamente a Silver."' in script.text
    assert 'Write-Host "Estado del servidor: $($SubmitResponse.status)"' in script.text
    assert 'Write-Host "Ahora podes volver a la pagina donde copiaste este script."' in script.text
    assert 'Write-Host "Esa pagina se actualiza sola y va a mostrar los resultados del reporte."' in script.text
    assert "Get-ChildItem" in script.text
    assert "ConvertFrom-Json" in script.text
    assert "Invoke-RestMethod" in script.text


def test_home_page_uses_spanish_copy_and_language_attribute():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert '<html lang="es">' in html
    assert "Para talento" in html
    assert "Enviar reporte" in html
    assert "metricas agregadas" in html
    assert "Importacion local" in html
    assert "Previsualizacion" in html
    assert "Volver a un envio anterior" in html
    assert "Link privado" in html
    assert "saved-report-row" in html
    assert "Borrar" in html
    assert "/delete?token=" in html
    assert "silverUsageReports" in html
    assert "Manual" not in html
    assert "Start report" not in html
    assert "For Talent" not in html


def test_report_status_page_requires_private_token_and_shows_management_actions():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)
    private_token = _private_token_from(response.text)

    denied = client.get(f"/reports/sessions/{session_id}/status")
    allowed = client.get(f"/reports/sessions/{session_id}/status", params={"token": private_token})

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert "Estado del reporte" in allowed.text
    assert "Codigo de sesion" in allowed.text
    assert "Eliminar datos del reporte" in allowed.text


def test_home_can_open_existing_report_from_private_link():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    management_url = _management_url_from(response.text)

    opened = client.post(
        "/reports/sessions/open",
        data={"management_url": management_url},
        follow_redirects=False,
    )

    assert opened.status_code == 303
    assert opened.headers["location"].startswith("/reports/sessions/session_")
    assert "?token=" in opened.headers["location"]


def test_web_flow_submits_and_deletes_report_after_external_preview():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)
    private_token = _private_token_from(response.text)

    preview = signed_post(
        client,
        f"/api/usage-report/sessions/{session_id}/preview",
        private_token,
        {
            "rows": [
                {
                    "provider": "openai",
                    "tool": "codex",
                    "source": "codex_local_telemetry",
                    "period_start": "2026-05-01T00:00:00Z",
                    "period_end": "2026-05-02T00:00:00Z",
                    "period_width": "1d",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cost_source": "unknown",
                    "confidence": "medium",
                }
            ]
        },
    )

    assert preview.status_code == 200

    submitted = client.post(f"/reports/sessions/{session_id}/submit", params={"token": private_token})

    assert submitted.status_code == 200
    assert "Reporte enviado" in submitted.text
    assert "150" in submitted.text

    deleted = client.post(f"/reports/sessions/{session_id}/delete", params={"token": private_token})

    assert deleted.status_code == 200
    assert "Reporte eliminado" in deleted.text
    assert "Collector local de Codex" in deleted.text
    assert "Datos compartidos con Silver" not in deleted.text


def test_report_session_preview_panel_updates_after_external_submit():
    client = TestClient(app)
    response = client.post("/reports/sessions")
    session_id = _session_id_from(response.text)
    private_token = _private_token_from(response.text)

    empty_panel = client.get(f"/reports/sessions/{session_id}/preview-panel", params={"token": private_token})

    assert empty_panel.status_code == 200
    assert "Proveedor, herramienta y modelo" in empty_panel.text

    preview = signed_post(
        client,
        f"/api/usage-report/sessions/{session_id}/preview",
        private_token,
        {
            "rows": [
                {
                    "provider": "openai",
                    "tool": "codex",
                    "source": "codex_local_telemetry",
                    "period_start": "2026-05-01T00:00:00Z",
                    "period_end": "2026-05-02T00:00:00Z",
                    "period_width": "1d",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cost_source": "unknown",
                    "confidence": "medium",
                }
            ]
        },
    )

    assert preview.status_code == 200

    updated_panel = client.get(f"/reports/sessions/{session_id}/preview-panel", params={"token": private_token})

    assert updated_panel.status_code == 200
    assert "Filas previsualizadas" in updated_panel.text
    assert "150" in updated_panel.text
    assert "Confirmar envio" in updated_panel.text
    assert "Modelo" in updated_panel.text
    assert "Requests" in updated_panel.text
    assert "Razonamiento" in updated_panel.text
    assert "No disponible en telemetria local" in updated_panel.text
    assert "Confianza" not in updated_panel.text
    assert "Este es el detalle completo del payload agregado" in updated_panel.text

    submitted = client.post(f"/reports/sessions/{session_id}/submit", params={"token": private_token})

    assert submitted.status_code == 200
    assert "Tu reporte de uso de IA" in submitted.text
    assert "Reporte enviado" in submitted.text

    submitted_panel = client.get(f"/reports/sessions/{session_id}/preview-panel", params={"token": private_token})

    assert submitted_panel.status_code == 204
    assert submitted_panel.headers["hx-redirect"] == f"/reports/sessions/{session_id}/report?token={private_token}"
