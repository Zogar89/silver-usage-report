import csv
from io import StringIO
from typing import Any

from app.schemas.usage_report import UsageReportRow


def parse_csv_rows(csv_text: str) -> list[UsageReportRow]:
    reader = csv.DictReader(StringIO(csv_text.strip()))
    return [UsageReportRow(**_clean_row(row)) for row in reader]


def parse_json_rows(data: Any) -> list[UsageReportRow]:
    if isinstance(data, dict) and "rows" in data:
        rows = data["rows"]
    else:
        rows = data
    if not isinstance(rows, list):
        raise ValueError("JSON import must be a list of rows or an object with rows")
    return [UsageReportRow(**row) for row in rows]


def _clean_row(row: dict[str, str | None]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if key is None or value is None or value == "":
            continue
        cleaned[key] = _coerce_value(key, value)
    return cleaned


def _coerce_value(key: str, value: str) -> int | float | str:
    if key.endswith("_tokens") or key == "request_count" or key == "total_tokens":
        return int(value)
    if key == "cost_usd":
        return float(value)
    return value
