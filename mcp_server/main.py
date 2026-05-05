import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, request

from app.adapters.codex_local import preview_codex_local_usage
from app.services.imports import parse_json_rows

HTTP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "silver-usage-report-mcp/0.1",
}


def preview_report(payload: Any) -> dict[str, object]:
    rows = parse_json_rows(payload)
    return {
        "row_count": len(rows),
        "total_tokens": sum(row.total_tokens or 0 for row in rows),
        "warnings": [],
    }


def preview_codex_local(logs_db_path: str) -> dict[str, object]:
    rows, warnings = preview_codex_local_usage(Path(logs_db_path))
    return {
        "row_count": len(rows),
        "total_tokens": sum(row.total_tokens or 0 for row in rows),
        "source": "codex_local_telemetry",
        "warnings": [warning.model_dump(mode="json") for warning in warnings],
    }


def submit_report(
    report_session_id: str,
    payload: Any,
    base_url: str = "http://localhost:8000",
    confirmed: bool = False,
) -> dict[str, object]:
    preview = preview_report(payload)
    if not confirmed:
        return {
            **preview,
            "status": "confirmation_required",
        }

    rows = parse_json_rows(payload)
    rows_json = [row.model_dump(mode="json") for row in rows]
    preview_url = f"{base_url.rstrip('/')}/api/usage-report/sessions/{report_session_id}/preview"
    submit_url = f"{base_url.rstrip('/')}/api/usage-report/sessions/{report_session_id}/submit"
    _post_json(preview_url, {"method": "POST", "json": {"rows": rows_json, "warnings": []}})

    confirmed_at = datetime.now(UTC).isoformat()
    submit_payload = {
        "report_session_id": report_session_id,
        "generated_at": confirmed_at,
        "rows": rows_json,
        "warnings": [],
        "user_confirmation": {
            "preview_shown": True,
            "confirmed_at": confirmed_at,
        },
    }
    _post_json(submit_url, {"method": "POST", "json": submit_payload})
    return {
        **preview,
        "status": "submitted",
    }


def submit_codex_local(
    report_session_id: str,
    logs_db_path: str,
    base_url: str = "http://localhost:8000",
    confirmed: bool = False,
) -> dict[str, object]:
    rows, warnings = preview_codex_local_usage(Path(logs_db_path))
    preview = {
        "row_count": len(rows),
        "total_tokens": sum(row.total_tokens or 0 for row in rows),
        "source": "codex_local_telemetry",
        "warnings": [warning.model_dump(mode="json") for warning in warnings],
    }
    if not confirmed:
        return {
            **preview,
            "status": "confirmation_required",
        }

    rows_json = [row.model_dump(mode="json") for row in rows]
    warnings_json = [warning.model_dump(mode="json") for warning in warnings]
    preview_url = f"{base_url.rstrip('/')}/api/usage-report/sessions/{report_session_id}/preview"
    submit_url = f"{base_url.rstrip('/')}/api/usage-report/sessions/{report_session_id}/submit"
    _post_json(preview_url, {"method": "POST", "json": {"rows": rows_json, "warnings": warnings_json}})

    confirmed_at = datetime.now(UTC).isoformat()
    submit_payload = {
        "report_session_id": report_session_id,
        "generated_at": confirmed_at,
        "rows": rows_json,
        "warnings": warnings_json,
        "user_confirmation": {
            "preview_shown": True,
            "confirmed_at": confirmed_at,
        },
    }
    _post_json(submit_url, {"method": "POST", "json": submit_payload})
    return {
        **preview,
        "status": "submitted",
    }


def get_report_status(
    report_session_id: str,
    base_url: str = "http://localhost:8000",
) -> dict[str, object]:
    status_url = f"{base_url.rstrip('/')}/api/usage-report/sessions/{report_session_id}"
    return _get_json(status_url)


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload["json"]).encode("utf-8")
    http_request = request.Request(
        url,
        data=body,
        method=payload.get("method", "POST"),
        headers=HTTP_HEADERS,
    )
    try:
        with request.urlopen(http_request, timeout=30) as response:
            return _decode_json_response(url, response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(_format_http_error(url, exc)) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Silver API request failed: could not reach {url}: {exc.reason}") from exc


def _get_json(url: str) -> dict[str, Any]:
    http_request = request.Request(url, method="GET", headers=HTTP_HEADERS)
    try:
        with request.urlopen(http_request, timeout=30) as response:
            return _decode_json_response(url, response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(_format_http_error(url, exc)) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Silver API request failed: could not reach {url}: {exc.reason}") from exc


def _decode_json_response(url: str, response_body: str) -> dict[str, Any]:
    if not response_body:
        return {}
    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Silver API request failed: invalid JSON response from {url}: {response_body}") from exc


def _format_http_error(url: str, exc: error.HTTPError) -> str:
    response_body = exc.read().decode("utf-8", "replace").strip()
    message = f"Silver API request failed: HTTP {exc.code} {exc.reason} for {url}"
    if response_body:
        message = f"{message}: {response_body}"
    return message
