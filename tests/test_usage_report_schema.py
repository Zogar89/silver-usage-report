from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.usage_report import (
    CostSource,
    Provider,
    ReportWarning,
    UsageReportPayload,
    UsageReportRow,
)


def test_usage_report_row_rejects_negative_tokens():
    with pytest.raises(ValidationError):
        UsageReportRow(
            provider=Provider.OPENAI,
            source="codex_local_telemetry",
            period_start="2026-05-01T00:00:00Z",
            period_end="2026-05-02T00:00:00Z",
            period_width="1d",
            input_tokens=-1,
            cost_source=CostSource.UNKNOWN,
            confidence="medium",
        )


def test_usage_report_row_rejects_inverted_periods():
    with pytest.raises(ValidationError):
        UsageReportRow(
            provider=Provider.ANTHROPIC,
            source="codex_local_telemetry",
            period_start="2026-05-02T00:00:00Z",
            period_end="2026-05-01T00:00:00Z",
            period_width="1d",
            total_tokens=100,
            cost_source=CostSource.UNKNOWN,
            confidence="medium",
        )


def test_usage_report_payload_accepts_previewed_confirmed_report():
    payload = UsageReportPayload(
        report_session_id="session_123",
        generated_at=datetime.now(UTC),
        rows=[
            UsageReportRow(
                provider=Provider.OPENAI,
                tool="codex",
                source="codex_local_telemetry",
                period_start="2026-05-01T00:00:00Z",
                period_end="2026-05-02T00:00:00Z",
                period_width="1d",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost_source=CostSource.UNKNOWN,
                confidence="medium",
            )
        ],
        warnings=[ReportWarning(code="codex_local_data", message="Codex local telemetry.")],
        user_confirmation={
            "preview_shown": True,
            "confirmed_at": datetime.now(UTC),
        },
    )

    assert payload.schema_version == "2026-05-04"
    assert payload.rows[0].total_tokens == 150


def test_usage_report_row_derives_total_tokens_when_missing():
    row = UsageReportRow(
        provider=Provider.OPENAI,
        source="codex_local_telemetry",
        period_start="2026-05-01T00:00:00Z",
        period_end="2026-05-02T00:00:00Z",
        period_width="1d",
        input_tokens=100,
        output_tokens=50,
        cached_input_tokens=25,
        reasoning_tokens=10,
        cost_source=CostSource.UNKNOWN,
        confidence="medium",
    )

    assert row.total_tokens == 185
    assert row.confidence == "medium"


def test_usage_report_rejects_sensitive_fields_recursively():
    with pytest.raises(ValidationError):
        UsageReportRow(
            provider=Provider.OPENAI,
            source="codex_local_telemetry",
            period_start="2026-05-01T00:00:00Z",
            period_end="2026-05-02T00:00:00Z",
            period_width="1d",
            total_tokens=100,
            cost_source=CostSource.UNKNOWN,
            confidence="medium",
            evidence={"warnings": [], "raw_log": "secret raw payload"},
        )
