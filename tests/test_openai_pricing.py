from app.schemas.usage_report import UsageReportRow
from app.services.openai_pricing import estimate_openai_cost, load_openai_price_table


def _row(**overrides) -> UsageReportRow:
    payload = {
        "provider": "openai",
        "tool": "codex",
        "source": "codex_local_telemetry",
        "period_start": "2026-05-01T00:00:00Z",
        "period_end": "2026-05-02T00:00:00Z",
        "period_width": "1d",
        "model": "gpt-5.5",
        "input_tokens": 1_000_000,
        "cached_input_tokens": 200_000,
        "output_tokens": 100_000,
        "cost_source": "unknown",
        "confidence": "medium",
    }
    payload.update(overrides)
    return UsageReportRow(**payload)


def test_local_openai_price_table_contains_current_codex_models():
    table = load_openai_price_table()

    assert table.price_for("gpt-5.5") is not None
    assert table.price_for("gpt-5.4") is not None
    assert table.price_for("gpt-5.3-codex") is not None
    assert table.source_url == "https://developers.openai.com/api/docs/pricing"


def test_estimate_openai_cost_uses_fresh_cached_and_output_rates():
    priced = estimate_openai_cost(_row(total_tokens=1_100_000))

    assert priced.cost_usd == 7.1
    assert priced.cost_source == "estimated"


def test_estimate_openai_cost_supports_separate_cached_input_semantics():
    priced = estimate_openai_cost(_row(total_tokens=1_300_000))

    assert priced.cost_usd == 8.1
    assert priced.cost_source == "estimated"


def test_estimate_openai_cost_leaves_unknown_models_unpriced():
    priced = estimate_openai_cost(_row(model="future-model"))

    assert priced.cost_usd is None
    assert priced.cost_source == "unknown"
