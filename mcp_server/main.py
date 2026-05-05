from typing import Any

from app.services.imports import parse_json_rows


def preview_report(payload: Any) -> dict[str, object]:
    rows = parse_json_rows(payload)
    return {
        "row_count": len(rows),
        "total_tokens": sum(row.total_tokens or 0 for row in rows),
        "warnings": [],
    }


def submit_report(payload: Any) -> dict[str, object]:
    preview = preview_report(payload)
    return {
        **preview,
        "status": "ready_for_api_submit",
    }


def get_report_status(report_session_id: str) -> dict[str, str]:
    return {
        "report_session_id": report_session_id,
        "status": "not_connected",
    }
