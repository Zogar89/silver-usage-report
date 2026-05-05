import argparse
import json
from pathlib import Path
from datetime import UTC, datetime
from typing import Any, Sequence
from urllib import request

from app.adapters.codex_local import preview_codex_local_usage
from app.services.imports import parse_csv_rows, parse_json_rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="silver-usage-report")
    subcommands = parser.add_subparsers(dest="command", required=True)

    preview = subcommands.add_parser("preview", help="Preview a normalized JSON report file.")
    preview.add_argument("file", type=Path)

    preview_csv = subcommands.add_parser("preview-csv", help="Preview a normalized CSV report file.")
    preview_csv.add_argument("file", type=Path)

    preview_codex = subcommands.add_parser(
        "preview-codex",
        help="Preview Codex local telemetry from an explicit logs_2.sqlite path.",
    )
    preview_codex.add_argument("--logs-db", required=True, type=Path)

    submit = subcommands.add_parser("submit", help="Preview and submit a JSON report to a session.")
    submit.add_argument("--session", required=True)
    submit.add_argument("--file", required=True, type=Path)
    submit.add_argument("--base-url", default="http://localhost:8000")
    submit.add_argument("--yes", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "preview":
        return _preview_json(args.file)
    if args.command == "preview-csv":
        return _preview_csv(args.file)
    if args.command == "preview-codex":
        return _preview_codex(args.logs_db)
    if args.command == "submit":
        return _submit(args.session, args.file, args.base_url, args.yes)
    return 1


def _preview_json(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = parse_json_rows(data)
    _print_preview(rows)
    return 0


def _preview_csv(path: Path) -> int:
    rows = parse_csv_rows(path.read_text(encoding="utf-8"))
    _print_preview(rows)
    return 0


def _preview_codex(logs_db_path: Path) -> int:
    rows, warnings = preview_codex_local_usage(logs_db_path)
    _print_preview(rows)
    print("Source: codex_local_telemetry")
    for warning in warnings:
        print(f"Warning: {warning.code} - {warning.message}")
    return 0


def _submit(session_id: str, path: Path, base_url: str, yes: bool) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = parse_json_rows(data)
    _print_preview(rows)
    if not yes:
        print("Refusing to submit without --yes")
        return 2

    rows_json = [row.model_dump(mode="json") for row in rows]
    preview_url = f"{base_url.rstrip('/')}/api/usage-report/sessions/{session_id}/preview"
    submit_url = f"{base_url.rstrip('/')}/api/usage-report/sessions/{session_id}/submit"
    _post_json(preview_url, {"method": "POST", "json": {"rows": rows_json, "warnings": []}})

    confirmed_at = datetime.now(UTC).isoformat()
    payload = {
        "report_session_id": session_id,
        "generated_at": confirmed_at,
        "rows": rows_json,
        "warnings": [],
        "user_confirmation": {
            "preview_shown": True,
            "confirmed_at": confirmed_at,
        },
    }
    _post_json(submit_url, {"method": "POST", "json": payload})
    print(f"Submitted report for session {session_id}")
    return 0


def _print_preview(rows) -> None:
    total_tokens = sum(row.total_tokens or 0 for row in rows)
    print(f"Rows: {len(rows)}")
    print(f"Total tokens: {total_tokens}")


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload["json"]).encode("utf-8")
    http_request = request.Request(
        url,
        data=body,
        method=payload.get("method", "POST"),
        headers={"content-type": "application/json"},
    )
    with request.urlopen(http_request, timeout=30) as response:
        response_body = response.read().decode("utf-8")
    if not response_body:
        return {}
    return json.loads(response_body)


if __name__ == "__main__":
    raise SystemExit(main())
