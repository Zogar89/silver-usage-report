import argparse
import json
from pathlib import Path
from datetime import UTC, datetime
from typing import Any, Sequence
from urllib import error, request

from app.adapters.codex_local import preview_codex_local_usage, preview_codex_sessions_usage
from app.services.imports import parse_csv_rows, parse_json_rows

HTTP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "silver-usage-report-cli/0.1",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="silver-usage-collector")
    subcommands = parser.add_subparsers(dest="command", required=True)

    preview = subcommands.add_parser("preview", help="Preview a normalized JSON report file.")
    preview.add_argument("file", type=Path)

    preview_csv = subcommands.add_parser("preview-csv", help="Preview a normalized CSV report file.")
    preview_csv.add_argument("file", type=Path)

    preview_codex = subcommands.add_parser(
        "preview-codex",
        help="Preview Codex local usage from a sessions directory or legacy SQLite path.",
    )
    preview_codex.add_argument("--sessions-dir", type=Path)
    preview_codex.add_argument("--state-db", type=Path)
    preview_codex.add_argument("--logs-db", type=Path)

    submit = subcommands.add_parser("submit", help="Preview and submit a JSON report to a session.")
    submit.add_argument("--session", required=True)
    submit.add_argument("--file", required=True, type=Path)
    submit.add_argument("--base-url", default="http://localhost:8000")
    submit.add_argument("--yes", action="store_true")

    submit_codex = subcommands.add_parser(
        "submit-codex",
        help="Preview and submit Codex local usage from a sessions directory or legacy SQLite path.",
    )
    submit_codex.add_argument("--session", required=True)
    submit_codex.add_argument("--sessions-dir", type=Path)
    submit_codex.add_argument("--state-db", type=Path)
    submit_codex.add_argument("--logs-db", type=Path)
    submit_codex.add_argument("--base-url", default="http://localhost:8000")
    submit_codex.add_argument("--yes", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "preview":
        return _preview_json(args.file)
    if args.command == "preview-csv":
        return _preview_csv(args.file)
    if args.command == "preview-codex":
        return _preview_codex(args.sessions_dir, args.state_db, args.logs_db)
    if args.command == "submit":
        return _submit(args.session, args.file, args.base_url, args.yes)
    if args.command == "submit-codex":
        return _submit_codex(args.session, args.sessions_dir, args.state_db, args.logs_db, args.base_url, args.yes)
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


def _preview_codex(sessions_dir: Path | None, state_db_path: Path | None, logs_db_path: Path | None) -> int:
    rows, warnings = _preview_codex_source(sessions_dir, state_db_path, logs_db_path)
    _print_preview(rows)
    print("Source: codex_local_telemetry")
    for warning in warnings:
        print(f"Warning: {warning.code} - {warning.message}")
    return 0


def _submit(session_id: str, path: Path, base_url: str, yes: bool) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = parse_json_rows(data)
    return _submit_rows(session_id, rows, [], base_url, yes, "report")


def _submit_codex(
    session_id: str,
    sessions_dir: Path | None,
    state_db_path: Path | None,
    logs_db_path: Path | None,
    base_url: str,
    yes: bool,
) -> int:
    rows, warnings = _preview_codex_source(sessions_dir, state_db_path, logs_db_path)
    return _submit_rows(session_id, rows, warnings, base_url, yes, "Codex local telemetry")


def _preview_codex_source(
    sessions_dir: Path | None,
    state_db_path: Path | None,
    logs_db_path: Path | None,
):
    if sessions_dir is not None:
        return preview_codex_sessions_usage(sessions_dir)
    if state_db_path is not None:
        return preview_codex_local_usage(state_db_path)
    if logs_db_path is not None:
        return preview_codex_local_usage(logs_db_path)
    raise SystemExit("submit-codex requires --sessions-dir, --state-db, or --logs-db")


def _submit_rows(session_id: str, rows, warnings, base_url: str, yes: bool, label: str) -> int:
    _print_preview(rows)
    if not yes and not _confirm_submission():
        print("Refusing to submit without --yes")
        return 2

    rows_json = [row.model_dump(mode="json") for row in rows]
    warnings_json = [warning.model_dump(mode="json") for warning in warnings]
    preview_url = f"{base_url.rstrip('/')}/api/usage-report/sessions/{session_id}/preview"
    submit_url = f"{base_url.rstrip('/')}/api/usage-report/sessions/{session_id}/submit"
    _post_json(preview_url, {"method": "POST", "json": {"rows": rows_json, "warnings": warnings_json}})

    confirmed_at = datetime.now(UTC).isoformat()
    payload = {
        "report_session_id": session_id,
        "generated_at": confirmed_at,
        "rows": rows_json,
        "warnings": warnings_json,
        "user_confirmation": {
            "preview_shown": True,
            "confirmed_at": confirmed_at,
        },
    }
    _post_json(submit_url, {"method": "POST", "json": payload})
    print(f"Submitted {label} for session {session_id}")
    return 0


def _confirm_submission() -> bool:
    print("Submit this report to Silver? [y/N] ", end="")
    try:
        answer = input().strip().lower()
    except (EOFError, OSError):
        print()
        return False
    return answer in {"y", "yes"}


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
        headers=HTTP_HEADERS,
    )
    try:
        with request.urlopen(http_request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", "replace").strip()
        message = f"Silver API request failed: HTTP {exc.code} {exc.reason} for {url}"
        if response_body:
            message = f"{message}: {response_body}"
        raise SystemExit(message) from exc
    if not response_body:
        return {}
    return json.loads(response_body)


if __name__ == "__main__":
    raise SystemExit(main())
