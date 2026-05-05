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
            source="manual",
            period_start="2026-05-01T00:00:00Z",
            period_end="2026-05-02T00:00:00Z",
            period_width="1d",
            input_tokens=-1,
            cost_source=CostSource.MANUAL,
            confidence="low",
        )


def test_usage_report_row_rejects_inverted_periods():
    with pytest.raises(ValidationError):
        UsageReportRow(
            provider=Provider.ANTHROPIC,
            source="manual",
            period_start="2026-05-02T00:00:00Z",
            period_end="2026-05-01T00:00:00Z",
            period_width="1d",
            total_tokens=100,
            cost_source=CostSource.MANUAL,
            confidence="low",
        )


def test_usage_report_payload_accepts_previewed_confirmed_report():
    payload = UsageReportPayload(
        report_session_id="session_123",
        generated_at=datetime.now(UTC),
        rows=[
            UsageReportRow(
                provider=Provider.OPENAI,
                tool="codex",
                source="manual",
                period_start="2026-05-01T00:00:00Z",
                period_end="2026-05-02T00:00:00Z",
                period_width="1d",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost_source=CostSource.MANUAL,
                confidence="low",
            )
        ],
        warnings=[ReportWarning(code="manual_data", message="Manual data is lower confidence.")],
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
        source="manual",
        period_start="2026-05-01T00:00:00Z",
        period_end="2026-05-02T00:00:00Z",
        period_width="1d",
        input_tokens=100,
        output_tokens=50,
        cached_input_tokens=25,
        reasoning_tokens=10,
        cost_source=CostSource.MANUAL,
        confidence="medium",
    )

    assert row.total_tokens == 185
    assert row.confidence == "low"


def test_usage_report_rejects_sensitive_fields_recursively():
    with pytest.raises(ValidationError):
        UsageReportRow(
            provider=Provider.OPENAI,
            source="manual",
            period_start="2026-05-01T00:00:00Z",
            period_end="2026-05-02T00:00:00Z",
            period_width="1d",
            total_tokens=100,
            cost_source=CostSource.MANUAL,
            confidence="low",
            evidence={"warnings": [], "raw_log": "secret raw payload"},
        )
