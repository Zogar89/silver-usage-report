import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.schemas.usage_report import CostSource, Provider, UsageReportRow

PRICE_TABLE_PATH = Path(__file__).resolve().parents[1] / "data" / "openai_model_prices.json"
TOKENS_PER_PRICE_UNIT = 1_000_000


@dataclass(frozen=True)
class OpenAIModelPrice:
    model: str
    input: float
    cached_input: float | None
    output: float
    processing_mode: str = "standard"
    context: str = "short"


@dataclass(frozen=True)
class OpenAIPriceTable:
    source_url: str
    source_retrieved_at: str
    unit: str
    prices: dict[str, OpenAIModelPrice]

    def price_for(self, model: str | None) -> OpenAIModelPrice | None:
        if not model:
            return None
        return self.prices.get(model.strip().lower())


@lru_cache(maxsize=1)
def load_openai_price_table(path: Path = PRICE_TABLE_PATH) -> OpenAIPriceTable:
    payload = json.loads(path.read_text(encoding="utf-8"))
    prices = {
        str(item["model"]).lower(): OpenAIModelPrice(
            model=item["model"],
            input=float(item["input"]),
            cached_input=float(item["cached_input"]) if item.get("cached_input") is not None else None,
            output=float(item["output"]),
            processing_mode=item.get("processing_mode", "standard"),
            context=item.get("context", "short"),
        )
        for item in payload["prices"]
    }
    return OpenAIPriceTable(
        source_url=payload["source_url"],
        source_retrieved_at=payload["source_retrieved_at"],
        unit=payload["unit"],
        prices=prices,
    )


def estimate_openai_cost(row: UsageReportRow) -> UsageReportRow:
    if row.provider != Provider.OPENAI:
        return row
    if row.cost_usd is not None:
        return row

    price = load_openai_price_table().price_for(row.model)
    if price is None:
        return row

    fresh_input_tokens, billable_cached_tokens = _billable_input_tokens(row)
    cached_input_rate = price.cached_input if price.cached_input is not None else price.input
    output_tokens = row.output_tokens or 0
    cost = (
        (fresh_input_tokens * price.input)
        + (billable_cached_tokens * cached_input_rate)
        + (output_tokens * price.output)
    ) / TOKENS_PER_PRICE_UNIT

    return row.model_copy(
        update={
            "cost_usd": round(cost, 6),
            "cost_source": CostSource.ESTIMATED,
        }
    )


def _billable_input_tokens(row: UsageReportRow) -> tuple[int, int]:
    input_tokens = row.input_tokens or 0
    cached_input_tokens = row.cached_input_tokens or 0
    billable_cached_tokens = min(cached_input_tokens, input_tokens)
    if _input_tokens_include_cache(row):
        return max(input_tokens - billable_cached_tokens, 0), billable_cached_tokens
    return input_tokens, cached_input_tokens


def _input_tokens_include_cache(row: UsageReportRow) -> bool:
    total_tokens = row.total_tokens
    input_tokens = row.input_tokens or 0
    cached_input_tokens = row.cached_input_tokens or 0
    output_tokens = row.output_tokens or 0
    reasoning_tokens = row.reasoning_tokens or 0
    if total_tokens is None:
        return True

    includes_cache_candidates = (
        input_tokens + output_tokens,
        input_tokens + output_tokens + reasoning_tokens,
    )
    separate_cache_candidates = (
        input_tokens + cached_input_tokens + output_tokens,
        input_tokens + cached_input_tokens + output_tokens + reasoning_tokens,
    )
    includes_delta = min(abs(total_tokens - candidate) for candidate in includes_cache_candidates)
    separate_delta = min(abs(total_tokens - candidate) for candidate in separate_cache_candidates)
    return includes_delta <= separate_delta


def estimate_report_rows_cost(rows: list[UsageReportRow]) -> list[UsageReportRow]:
    return [estimate_openai_cost(row) for row in rows]
