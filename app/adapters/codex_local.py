import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.schemas.usage_report import EvidenceMetadata, ReportWarning, UsageReportRow

ADAPTER_NAME = "codex_local_telemetry"
ADAPTER_VERSION = "0.1.0"
USAGE_MARKER = "post sampling token usage"
INTERNAL_USAGE_MARKERS = {"auto-review", "internal_approval", "approval"}


def preview_codex_local_usage(logs_db_path: Path) -> tuple[list[UsageReportRow], list[ReportWarning]]:
    events = _read_usage_events(logs_db_path)
    external_events = [event for event in events if not _is_internal_usage(event)]
    internal_count = len(events) - len(external_events)
    rows = [_event_to_row(event, row_count=len(external_events)) for event in external_events]
    warnings: list[ReportWarning] = []
    if internal_count:
        warnings.append(
            ReportWarning(
                provider="openai",
                tool="codex",
                code="codex_internal_usage_excluded",
                message=f"Excluded {internal_count} Codex internal usage event(s).",
            )
        )
    if not rows:
        warnings.append(
            ReportWarning(
                provider="openai",
                tool="codex",
                code="codex_no_usage_rows",
                message="No Codex local token usage rows were found.",
            )
        )
    return rows, warnings


def _read_usage_events(logs_db_path: Path) -> list[dict[str, Any]]:
    connection = sqlite3.connect(logs_db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            select timestamp, feedback_log_body
            from logs
            where target = ?
              and feedback_log_body like ?
            order by timestamp asc
            """,
            ("codex_core::session::turn", f"%{USAGE_MARKER}%"),
        ).fetchall()
    finally:
        connection.close()

    events: list[dict[str, Any]] = []
    for row in rows:
        parsed = _parse_body(row["feedback_log_body"])
        if parsed is None:
            continue
        parsed["_timestamp"] = row["timestamp"]
        events.append(parsed)
    return events


def _parse_body(body: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    if USAGE_MARKER not in json.dumps(parsed):
        return None
    return parsed


def _is_internal_usage(event: dict[str, Any]) -> bool:
    serialized = json.dumps(event).lower()
    return any(marker in serialized for marker in INTERNAL_USAGE_MARKERS)


def _event_to_row(event: dict[str, Any], row_count: int) -> UsageReportRow:
    timestamp = _parse_timestamp(str(event.get("_timestamp")))
    return UsageReportRow(
        provider="openai",
        tool="codex",
        source="codex_local_telemetry",
        period_start=timestamp.isoformat(),
        period_end=(timestamp + timedelta(seconds=1)).isoformat(),
        period_width="custom",
        model=_optional_str(event.get("model")),
        request_count=1,
        input_tokens=_optional_int(event.get("input_tokens")),
        output_tokens=_optional_int(event.get("output_tokens")),
        cached_input_tokens=_optional_int(event.get("cached_input_tokens")),
        cache_creation_input_tokens=_optional_int(event.get("cache_creation_input_tokens")),
        reasoning_tokens=_optional_int(event.get("reasoning_tokens")),
        total_tokens=_optional_int(event.get("total_tokens")),
        cost_source="unknown",
        confidence="medium",
        evidence=EvidenceMetadata(
            adapter=ADAPTER_NAME,
            adapter_version=ADAPTER_VERSION,
            row_count=row_count,
            query_fingerprint="codex_core_session_turn_post_sampling_token_usage_v1",
            warnings=[],
        ),
    )


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
