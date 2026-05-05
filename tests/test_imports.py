import pytest
from pydantic import ValidationError

from app.services.imports import parse_csv_rows, parse_json_rows


def test_parse_csv_rows_returns_normalized_usage_rows():
    rows = parse_csv_rows(
        """provider,tool,source,period_start,period_end,period_width,input_tokens,output_tokens,cost_source,confidence
openai,codex,csv,2026-05-01T00:00:00Z,2026-05-02T00:00:00Z,1d,100,50,manual,medium
"""
    )

    assert len(rows) == 1
    assert rows[0].provider == "openai"
    assert rows[0].source == "csv"
    assert rows[0].total_tokens == 150
    assert rows[0].confidence == "medium"


def test_parse_json_rows_accepts_payload_shape():
    rows = parse_json_rows(
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
        }
    )

    assert rows[0].source == "json"
    assert rows[0].total_tokens == 150


def test_parse_json_rows_rejects_sensitive_fields():
    with pytest.raises(ValidationError):
        parse_json_rows(
            [
                {
                    "provider": "openai",
                    "source": "json",
                    "period_start": "2026-05-01T00:00:00Z",
                    "period_end": "2026-05-02T00:00:00Z",
                    "period_width": "1d",
                    "total_tokens": 150,
                    "cost_source": "manual",
                    "confidence": "medium",
                    "prompt": "do not send this",
                }
            ]
        )
