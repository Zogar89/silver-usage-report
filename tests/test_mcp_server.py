from unittest.mock import patch

from mcp_server.main import get_report_status, preview_report, submit_report


def test_mcp_preview_report_returns_totals_without_sensitive_data():
    result = preview_report(
        {
            "rows": [
                {
                    "provider": "openai",
                    "source": "json",
                    "period_start": "2026-05-01T00:00:00Z",
                    "period_end": "2026-05-02T00:00:00Z",
                    "period_width": "1d",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cost_source": "manual",
                    "confidence": "medium",
                }
            ]
        }
    )

    assert result == {
        "row_count": 1,
        "total_tokens": 150,
        "warnings": [],
    }


def test_mcp_submit_report_posts_preview_and_submit():
    calls: list[tuple[str, str, dict]] = []

    def fake_post(url: str, payload: dict) -> dict:
        calls.append((url, payload["method"], payload["json"]))
        return {"status": "ok"}

    with patch("mcp_server.main._post_json", side_effect=fake_post):
        result = submit_report(
            "session_123",
            {
                "rows": [
                    {
                        "provider": "openai",
                        "source": "json",
                        "period_start": "2026-05-01T00:00:00Z",
                        "period_end": "2026-05-02T00:00:00Z",
                        "period_width": "1d",
                        "total_tokens": 150,
                        "cost_source": "manual",
                        "confidence": "medium",
                    }
                ]
            },
            base_url="http://localhost:8000",
            confirmed=True,
        )

    assert result["status"] == "submitted"
    assert calls[0][0].endswith("/api/usage-report/sessions/session_123/preview")
    assert calls[1][0].endswith("/api/usage-report/sessions/session_123/submit")


def test_mcp_submit_report_requires_confirmation():
    result = submit_report("session_123", {"rows": []}, confirmed=False)

    assert result["status"] == "confirmation_required"


def test_mcp_get_report_status_uses_api():
    with patch("mcp_server.main._get_json", return_value={"status": "previewed", "row_count": 1}):
        result = get_report_status("session_123", base_url="http://localhost:8000")

    assert result == {"status": "previewed", "row_count": 1}
