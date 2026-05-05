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


def preview_codex_sessions_usage(
    sessions_dir: Path,
    since: datetime | None = None,
    aggregate: bool = False,
) -> tuple[list[UsageReportRow], list[ReportWarning]]:
    events = _read_session_usage_events(sessions_dir)
    events = _filter_events_since(events, since)
    rows = _events_to_rows(events, aggregate=aggregate)
    warnings: list[ReportWarning] = []
    if not rows:
        warnings.append(
            ReportWarning(
                provider="openai",
                tool="codex",
                code="codex_no_usage_rows",
                message="No se encontraron filas locales de uso de Codex.",
            )
        )
    return rows, warnings


def preview_codex_local_usage(
    logs_db_path: Path,
    since: datetime | None = None,
    aggregate: bool = False,
) -> tuple[list[UsageReportRow], list[ReportWarning]]:
    state_db_path = _state_db_for(logs_db_path)
    events = _read_state_events(state_db_path) if state_db_path else _read_usage_events(logs_db_path)
    external_events = [event for event in events if not _is_internal_usage(event)]
    internal_count = len(events) - len(external_events)
    external_events = _filter_events_since(external_events, since)
    rows = _events_to_rows(external_events, aggregate=aggregate)
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


def _events_to_rows(events: list[dict[str, Any]], aggregate: bool) -> list[UsageReportRow]:
    if aggregate:
        return _aggregate_daily_model_rows(events)
    return [_event_to_row(event, row_count=len(events)) for event in events]


def _filter_events_since(events: list[dict[str, Any]], since: datetime | None) -> list[dict[str, Any]]:
    if since is None:
        return events
    since_utc = since.astimezone(UTC) if since.tzinfo else since.replace(tzinfo=UTC)
    return [event for event in events if _parse_timestamp(str(event.get("_timestamp"))) >= since_utc]


def _aggregate_daily_model_rows(events: list[dict[str, Any]]) -> list[UsageReportRow]:
    grouped: dict[tuple[datetime, str | None], list[dict[str, Any]]] = {}
    for event in events:
        timestamp = _parse_timestamp(str(event.get("_timestamp")))
        day_start = datetime(timestamp.year, timestamp.month, timestamp.day, tzinfo=UTC)
        key = (day_start, _optional_str(event.get("model")))
        grouped.setdefault(key, []).append(event)

    rows: list[UsageReportRow] = []
    for (day_start, model), group in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1] or "")):
        rows.append(
            UsageReportRow(
                provider="openai",
                tool="codex",
                source="codex_local_telemetry",
                period_start=day_start.isoformat(),
                period_end=(day_start + timedelta(days=1)).isoformat(),
                period_width="1d",
                model=model,
                request_count=len(group),
                input_tokens=_sum_optional(group, "input_tokens"),
                output_tokens=_sum_optional(group, "output_tokens"),
                cached_input_tokens=_sum_optional(group, "cached_input_tokens"),
                cache_creation_input_tokens=_sum_optional(group, "cache_creation_input_tokens"),
                reasoning_tokens=_sum_optional(group, "reasoning_tokens"),
                total_tokens=sum(_event_total(event) or 0 for event in group),
                cost_source="unknown",
                confidence="medium",
                evidence=EvidenceMetadata(
                    adapter=ADAPTER_NAME,
                    adapter_version=ADAPTER_VERSION,
                    row_count=len(events),
                    query_fingerprint=_aggregate_query_fingerprint(group),
                    warnings=[],
                ),
            )
        )
    return rows


def _aggregate_query_fingerprint(events: list[dict[str, Any]]) -> str:
    source_fingerprint = _optional_str(events[0].get("_query_fingerprint")) if events else None
    if source_fingerprint == "codex_state_threads_tokens_used_v1":
        return "codex_state_daily_model_usage_v1"
    if source_fingerprint == "codex_sessions_token_count_total_usage_v1":
        return "codex_sessions_daily_model_usage_v1"
    return "codex_logs_daily_model_usage_v1"


def _sum_optional(events: list[dict[str, Any]], key: str) -> int | None:
    values = [_optional_int(event.get(key)) for event in events]
    known_values = [value for value in values if value is not None]
    if not known_values:
        return None
    return sum(known_values)


def _event_total(event: dict[str, Any]) -> int | None:
    explicit_total = _optional_int(event.get("total_tokens"))
    if explicit_total is not None:
        return explicit_total
    values = [
        _optional_int(event.get("input_tokens")),
        _optional_int(event.get("output_tokens")),
        _optional_int(event.get("cached_input_tokens")),
        _optional_int(event.get("cache_creation_input_tokens")),
        _optional_int(event.get("reasoning_tokens")),
    ]
    total = sum(value or 0 for value in values)
    return total if total else None


def _read_session_usage_events(sessions_dir: Path) -> list[dict[str, Any]]:
    if not sessions_dir.exists():
        return []

    events: list[dict[str, Any]] = []
    for path in sorted(sessions_dir.rglob("rollout-*.jsonl")):
        latest_event: dict[str, Any] | None = None
        metadata: dict[str, Any] = {}
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if '"model"' in line or '"model_provider"' in line or '"model_context_window"' in line:
                metadata.update(_parse_session_metadata_line(line))
            parsed = _parse_session_line(line)
            if parsed is not None:
                latest_event = parsed
        if latest_event is not None:
            if not latest_event.get("model") and metadata.get("model"):
                latest_event["model"] = metadata["model"]
            if not latest_event.get("model_provider") and metadata.get("model_provider"):
                latest_event["model_provider"] = metadata["model_provider"]
            if not latest_event.get("model_context_window") and metadata.get("model_context_window"):
                latest_event["model_context_window"] = metadata["model_context_window"]
            events.append(latest_event)
    row_count = len(events)
    for event in events:
        event["_row_count"] = row_count
    return events


def _parse_session_line(line: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None

    usage = parsed.get("usage")
    info = None
    rate_limits = parsed.get("rate_limits")
    if not isinstance(usage, dict):
        payload = parsed.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "token_count":
            info = payload.get("info")
            if isinstance(info, dict):
                usage = info.get("total_token_usage")
            rate_limits = payload.get("rate_limits")
    if not isinstance(usage, dict):
        return None
    if not _has_token_usage(usage):
        return None

    return {
        "_timestamp": _optional_str(parsed.get("timestamp")) or datetime.now(UTC).isoformat(),
        "_query_fingerprint": "codex_sessions_token_count_total_usage_v1",
        "message": USAGE_MARKER,
        "model": _optional_str(parsed.get("model")),
        "model_provider": _optional_str(parsed.get("model_provider")),
        "model_context_window": _optional_int(info.get("model_context_window")) if isinstance(info, dict) else None,
        "plan_type": _optional_str(rate_limits.get("plan_type")) if isinstance(rate_limits, dict) else None,
        "rate_limit_primary_used_percent": _nested_float(rate_limits, "primary", "used_percent"),
        "rate_limit_secondary_used_percent": _nested_float(rate_limits, "secondary", "used_percent"),
        "input_tokens": _usage_int(usage, "input_tokens"),
        "output_tokens": _usage_int(usage, "output_tokens"),
        "cached_input_tokens": _usage_int(usage, "cached_input_tokens"),
        "cache_creation_input_tokens": _usage_int(usage, "cache_creation_input_tokens"),
        "reasoning_tokens": _usage_int(usage, "reasoning_tokens", "reasoning_output_tokens"),
        "total_tokens": _usage_total(usage),
    }


def _parse_session_metadata_line(line: str) -> dict[str, Any]:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    payload = parsed.get("payload")
    if not isinstance(payload, dict):
        return {}
    metadata: dict[str, Any] = {}
    model = _optional_str(payload.get("model"))
    model_provider = _optional_str(payload.get("model_provider"))
    model_context_window = _optional_int(payload.get("model_context_window"))
    if model:
        metadata["model"] = model
    if model_provider:
        metadata["model_provider"] = model_provider
    if model_context_window is not None:
        metadata["model_context_window"] = model_context_window
    return metadata


def _has_token_usage(usage: dict[str, Any]) -> bool:
    return any(
        usage.get(key) not in (None, "")
        for key in (
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "cache_creation_input_tokens",
            "reasoning_tokens",
            "reasoning_output_tokens",
            "total_tokens",
        )
    )


def _usage_int(usage: dict[str, Any], key: str, *aliases: str) -> int | None:
    for candidate in (key, *aliases):
        value = _optional_int(usage.get(candidate))
        if value is not None:
            return value
    return None


def _usage_total(usage: dict[str, Any]) -> int | None:
    explicit_total = _usage_int(usage, "total_tokens")
    if explicit_total is not None:
        return explicit_total
    values = [
        _usage_int(usage, "input_tokens"),
        _usage_int(usage, "output_tokens"),
        _usage_int(usage, "cached_input_tokens"),
        _usage_int(usage, "cache_creation_input_tokens"),
        _usage_int(usage, "reasoning_tokens", "reasoning_output_tokens"),
    ]
    total = sum(value or 0 for value in values)
    return total if total else None


def _nested_float(value: Any, *keys: str) -> float | None:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current in (None, ""):
        return None
    try:
        return float(current)
    except (TypeError, ValueError):
        return None


def _state_db_for(logs_db_path: Path) -> Path | None:
    if logs_db_path.name == "state_5.sqlite" and logs_db_path.exists():
        return logs_db_path
    sibling = logs_db_path.with_name("state_5.sqlite")
    if sibling.exists():
        return sibling
    return None


def _read_state_events(state_db_path: Path) -> list[dict[str, Any]]:
    connection = sqlite3.connect(state_db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            select created_at, updated_at, created_at_ms, updated_at_ms, model, tokens_used
            from threads
            where tokens_used is not null
              and tokens_used > 0
            order by created_at asc
            """
        ).fetchall()
    finally:
        connection.close()

    events: list[dict[str, Any]] = []
    row_count = len(rows)
    for row in rows:
        events.append(
            {
                "_timestamp": _epoch_row_timestamp(row, "created_at"),
                "_period_end": _epoch_row_timestamp(row, "updated_at"),
                "_row_count": row_count,
                "_query_fingerprint": "codex_state_threads_tokens_used_v1",
                "message": USAGE_MARKER,
                "model": _optional_str(row["model"]),
                "total_tokens": _optional_int(row["tokens_used"]),
            }
        )
    return events


def _read_usage_events(logs_db_path: Path) -> list[dict[str, Any]]:
    connection = sqlite3.connect(logs_db_path)
    connection.row_factory = sqlite3.Row
    try:
        columns = _logs_columns(connection)
        rows = _query_usage_rows(connection, columns)
    finally:
        connection.close()

    events: list[dict[str, Any]] = []
    for row in rows:
        parsed = _parse_body(row["feedback_log_body"])
        if parsed is None:
            continue
        parsed["_timestamp"] = _timestamp_from_row(row)
        events.append(parsed)
    return events


def _logs_columns(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("pragma table_info(logs)").fetchall()
    return {str(row["name"]) for row in rows}


def _query_usage_rows(connection: sqlite3.Connection, columns: set[str]) -> list[sqlite3.Row]:
    if "timestamp" in columns:
        return connection.execute(
            """
            select timestamp, feedback_log_body
            from logs
            where target = ?
              and feedback_log_body like ?
            order by timestamp asc
            """,
            ("codex_core::session::turn", f"%{USAGE_MARKER}%"),
        ).fetchall()

    if "ts" in columns:
        ts_nanos_select = "ts_nanos" if "ts_nanos" in columns else "0 as ts_nanos"
        return connection.execute(
            f"""
            select ts, {ts_nanos_select}, feedback_log_body
            from logs
            where target = ?
              and feedback_log_body like ?
            order by ts asc, ts_nanos asc
            """,
            ("codex_core::session::turn", f"%{USAGE_MARKER}%"),
        ).fetchall()

    raise sqlite3.OperationalError("unsupported Codex logs schema: expected timestamp or ts column")


def _timestamp_from_row(row: sqlite3.Row) -> str:
    keys = set(row.keys())
    if "timestamp" in keys:
        return str(row["timestamp"])
    seconds = int(row["ts"])
    nanos = int(row["ts_nanos"] or 0)
    return datetime.fromtimestamp(seconds + (nanos / 1_000_000_000), UTC).isoformat()


def _epoch_row_timestamp(row: sqlite3.Row, seconds_key: str) -> str:
    milliseconds_key = f"{seconds_key}_ms"
    keys = set(row.keys())
    if milliseconds_key in keys and row[milliseconds_key] not in (None, ""):
        return datetime.fromtimestamp(int(row[milliseconds_key]) / 1000, UTC).isoformat()
    return datetime.fromtimestamp(int(row[seconds_key]), UTC).isoformat()


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
    period_end = _parse_timestamp(str(event.get("_period_end"))) if event.get("_period_end") else timestamp + timedelta(seconds=1)
    return UsageReportRow(
        provider="openai",
        tool="codex",
        source="codex_local_telemetry",
        period_start=timestamp.isoformat(),
        period_end=period_end.isoformat(),
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
            row_count=_optional_int(event.get("_row_count")) or row_count,
            query_fingerprint=_optional_str(event.get("_query_fingerprint"))
            or "codex_core_session_turn_post_sampling_token_usage_v1",
            model_context_window=_optional_int(event.get("model_context_window")),
            plan_type=_optional_str(event.get("plan_type")),
            rate_limit_primary_used_percent=_nested_float(event, "rate_limit_primary_used_percent"),
            rate_limit_secondary_used_percent=_nested_float(event, "rate_limit_secondary_used_percent"),
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
