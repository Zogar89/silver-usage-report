from mcp_server.main import preview_report


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
