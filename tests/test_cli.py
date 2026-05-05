import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

import cli.main as cli_main
from cli.main import main


def test_cli_preview_validates_json_report_file(capsys):
    report_file = Path(".tmp_cli_report.json")
    try:
        report_file.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "provider": "openai",
                            "source": "json",
                            "period_start": "2026-05-01T00:00:00Z",
                            "period_end": "2026-05-02T00:00:00Z",
                            "period_width": "1d",
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "cost_source": "manual",
                            "confidence": "medium",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        exit_code = main(["preview", str(report_file)])

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Rows: 1" in output
        assert "Total tokens: 150" in output
    finally:
        report_file.unlink(missing_ok=True)


def test_cli_help_uses_collector_program_name(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert output.startswith("usage: silver-usage-collector")


def test_cli_preview_csv_validates_csv_report_file(capsys):
    report_file = Path(".tmp_cli_report.csv")
    try:
        report_file.write_text(
            "provider,source,period_start,period_end,period_width,input_tokens,output_tokens,cost_source,confidence\n"
            "openai,csv,2026-05-01T00:00:00Z,2026-05-02T00:00:00Z,1d,100,50,manual,medium\n",
            encoding="utf-8",
        )

        exit_code = main(["preview-csv", str(report_file)])

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Rows: 1" in output
        assert "Total tokens: 150" in output
    finally:
        report_file.unlink(missing_ok=True)


def test_cli_submit_requires_yes_confirmation(capsys):
    report_file = Path(".tmp_cli_submit.json")
    try:
        report_file.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "provider": "openai",
                            "source": "json",
                            "period_start": "2026-05-01T00:00:00Z",
                            "period_end": "2026-05-02T00:00:00Z",
                            "period_width": "1d",
                            "total_tokens": 150,
                            "cost_source": "manual",
                            "confidence": "medium",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        exit_code = main(
            [
                "submit",
                "--session",
                "session_123",
                "--file",
                str(report_file),
                "--base-url",
                "http://localhost:8000",
            ]
        )

        assert exit_code == 2
        assert "Refusing to submit without --yes" in capsys.readouterr().out
    finally:
        report_file.unlink(missing_ok=True)


def test_cli_submit_previews_then_posts_report(capsys):
    report_file = Path(".tmp_cli_submit.json")
    calls: list[tuple[str, str, dict]] = []
    try:
        report_file.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "provider": "openai",
                            "source": "json",
                            "period_start": "2026-05-01T00:00:00Z",
                            "period_end": "2026-05-02T00:00:00Z",
                            "period_width": "1d",
                            "total_tokens": 150,
                            "cost_source": "manual",
                            "confidence": "medium",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        def fake_post(url: str, payload: dict) -> dict:
            calls.append((url, payload["method"], payload["json"]))
            return {"status": "ok"}

        with patch("cli.main._post_json", side_effect=fake_post):
            exit_code = main(
                [
                    "submit",
                    "--session",
                    "session_123",
                    "--file",
                    str(report_file),
                    "--base-url",
                    "http://localhost:8000",
                    "--yes",
                ]
            )

        assert exit_code == 0
        assert calls[0][0].endswith("/api/usage-report/sessions/session_123/preview")
        assert calls[1][0].endswith("/api/usage-report/sessions/session_123/submit")
        assert calls[1][2]["user_confirmation"]["preview_shown"] is True
        assert "Submitted report for session session_123" in capsys.readouterr().out
    finally:
        report_file.unlink(missing_ok=True)


def test_cli_submit_accepts_interactive_confirmation(capsys):
    report_file = Path(".tmp_cli_submit_interactive.json")
    calls: list[tuple[str, str, dict]] = []
    try:
        report_file.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "provider": "openai",
                            "source": "json",
                            "period_start": "2026-05-01T00:00:00Z",
                            "period_end": "2026-05-02T00:00:00Z",
                            "period_width": "1d",
                            "total_tokens": 150,
                            "cost_source": "manual",
                            "confidence": "medium",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        def fake_post(url: str, payload: dict) -> dict:
            calls.append((url, payload["method"], payload["json"]))
            return {"status": "ok"}

        with (
            patch("builtins.input", return_value="y"),
            patch("cli.main._post_json", side_effect=fake_post),
        ):
            exit_code = main(
                [
                    "submit",
                    "--session",
                    "session_123",
                    "--file",
                    str(report_file),
                    "--base-url",
                    "http://localhost:8000",
                ]
            )

        assert exit_code == 0
        assert len(calls) == 2
        assert "Submit this report to Silver? [y/N]" in capsys.readouterr().out
    finally:
        report_file.unlink(missing_ok=True)


def test_cli_preview_codex_reads_explicit_logs_db(capsys):
    db_path = Path(".tmp_cli_codex_logs.sqlite")
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "create table logs (target text not null, timestamp text not null, feedback_log_body text not null)"
        )
        connection.execute(
            "insert into logs (target, timestamp, feedback_log_body) values (?, ?, ?)",
            (
                "codex_core::session::turn",
                "2026-05-01T10:00:00Z",
                json.dumps(
                    {
                        "message": "post sampling token usage",
                        "model": "gpt-5.5",
                        "input_tokens": 100,
                        "output_tokens": 50,
                    }
                ),
            ),
        )
        connection.commit()
        connection.close()

        exit_code = main(["preview-codex", "--logs-db", str(db_path)])

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Rows: 1" in output
        assert "Total tokens: 150" in output
        assert "Source: codex_local_telemetry" in output
    finally:
        connection.close()
        db_path.unlink(missing_ok=True)


def test_cli_preview_codex_reads_sessions_dir(capsys):
    sessions_dir = Path(".tmp_cli_codex_sessions")
    rollout_dir = sessions_dir / "2026" / "04" / "25"
    rollout_dir.mkdir(parents=True, exist_ok=True)
    rollout_path = rollout_dir / "rollout-2026-04-25T05-21-56-thread.jsonl"
    try:
        rollout_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-04-25T05:21:56Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 100,
                                "output_tokens": 50,
                                "total_tokens": 150,
                            }
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

        exit_code = main(["preview-codex", "--sessions-dir", str(sessions_dir)])

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Rows: 1" in output
        assert "Total tokens: 150" in output
        assert "Source: codex_local_telemetry" in output
    finally:
        rollout_path.unlink(missing_ok=True)
        rollout_dir.rmdir()
        (sessions_dir / "2026" / "04").rmdir()
        (sessions_dir / "2026").rmdir()
        sessions_dir.rmdir()


def test_cli_preview_codex_defaults_to_last_30_days_and_prints_usage_breakdown(capsys):
    sessions_dir = Path(".tmp_cli_codex_recent_sessions")
    recent = datetime.now(UTC) - timedelta(days=1)
    old = datetime.now(UTC) - timedelta(days=45)
    recent_dir = sessions_dir / recent.strftime("%Y") / recent.strftime("%m") / recent.strftime("%d")
    old_dir = sessions_dir / old.strftime("%Y") / old.strftime("%m") / old.strftime("%d")
    recent_dir.mkdir(parents=True, exist_ok=True)
    old_dir.mkdir(parents=True, exist_ok=True)
    recent_path = recent_dir / "rollout-recent.jsonl"
    old_path = old_dir / "rollout-old.jsonl"
    try:
        recent_path.write_text(
            json.dumps(
                {
                    "timestamp": recent.isoformat(),
                    "model": "gpt-5.5",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 100,
                                "cached_input_tokens": 25,
                                "output_tokens": 50,
                                "reasoning_output_tokens": 10,
                                "total_tokens": 185,
                            }
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        old_path.write_text(
            json.dumps(
                {
                    "timestamp": old.isoformat(),
                    "model": "gpt-5.5",
                    "payload": {
                        "type": "token_count",
                        "info": {"total_token_usage": {"input_tokens": 999, "total_tokens": 999}},
                    },
                }
            ),
            encoding="utf-8",
        )

        exit_code = main(["preview-codex", "--sessions-dir", str(sessions_dir)])

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Rows: 1" in output
        assert "Requests: 1" in output
        assert "Input tokens: 100" in output
        assert "Cached input tokens: 25" in output
        assert "Output tokens: 50" in output
        assert "Reasoning tokens: 10" in output
        assert "Total tokens: 185" in output
        assert "Top models:" in output
        assert "- gpt-5.5: 185 tokens, 1 requests" in output
        assert "Uso por dia:" in output
        assert "- 2026-" in output
        assert "185 tokens, 1 requests, in 100, out 50" in output
    finally:
        recent_path.unlink(missing_ok=True)
        old_path.unlink(missing_ok=True)
        old_dir.rmdir()
        recent_dir.rmdir()
        for path in sorted(sessions_dir.rglob("*"), reverse=True):
            if path.is_dir():
                path.rmdir()
        sessions_dir.rmdir()


def test_cli_submit_codex_requires_yes_confirmation(capsys):
    db_path = Path(".tmp_cli_codex_submit_requires.sqlite")
    connection = sqlite3.connect(db_path)
    try:
        _write_codex_usage_row(connection)

        exit_code = main(
            [
                "submit-codex",
                "--session",
                "session_123",
                "--logs-db",
                str(db_path),
                "--base-url",
                "http://localhost:8000",
            ]
        )

        assert exit_code == 2
        assert "Refusing to submit without --yes" in capsys.readouterr().out
    finally:
        connection.close()
        db_path.unlink(missing_ok=True)


def test_cli_submit_codex_previews_then_posts_report(capsys):
    db_path = Path(".tmp_cli_codex_submit.sqlite")
    calls: list[tuple[str, str, dict]] = []
    connection = sqlite3.connect(db_path)
    try:
        _write_codex_usage_row(connection)

        def fake_post(url: str, payload: dict) -> dict:
            calls.append((url, payload["method"], payload["json"]))
            return {"status": "ok"}

        with patch("cli.main._post_json", side_effect=fake_post):
            exit_code = main(
                [
                    "submit-codex",
                    "--session",
                    "session_123",
                    "--logs-db",
                    str(db_path),
                    "--base-url",
                    "http://localhost:8000",
                    "--yes",
                ]
            )

        assert exit_code == 0
        assert calls[0][0].endswith("/api/usage-report/sessions/session_123/preview")
        assert calls[0][2]["rows"][0]["source"] == "codex_local_telemetry"
        assert calls[1][0].endswith("/api/usage-report/sessions/session_123/submit")
        assert "Submitted Codex local telemetry for session session_123" in capsys.readouterr().out
    finally:
        connection.close()
        db_path.unlink(missing_ok=True)


def test_cli_post_json_identifies_itself_to_http_proxies():
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return b"{}"

    def fake_urlopen(http_request, timeout):
        captured["user_agent"] = http_request.get_header("User-agent")
        captured["accept"] = http_request.get_header("Accept")
        captured["timeout"] = timeout
        return FakeResponse()

    with patch("cli.main.request.urlopen", side_effect=fake_urlopen):
        result = cli_main._post_json("https://example.test/api", {"method": "POST", "json": {"rows": []}})

    assert result == {}
    assert captured["user_agent"] == "silver-usage-report-cli/0.1"
    assert captured["accept"] == "application/json"
    assert captured["timeout"] == 30


def test_cli_post_json_reports_network_errors():
    with patch("cli.main.request.urlopen", side_effect=cli_main.error.URLError("connection refused")):
        with pytest.raises(SystemExit) as exc:
            cli_main._post_json("https://example.test/api", {"method": "POST", "json": {"rows": []}})

    assert "Silver API request failed: could not reach https://example.test/api" in str(exc.value)
    assert "connection refused" in str(exc.value)


def test_cli_post_json_reports_invalid_json_response():
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return b"<html>proxy login</html>"

    with patch("cli.main.request.urlopen", return_value=FakeResponse()):
        with pytest.raises(SystemExit) as exc:
            cli_main._post_json("https://example.test/api", {"method": "POST", "json": {"rows": []}})

    assert "Silver API request failed: invalid JSON response from https://example.test/api" in str(exc.value)


def _write_codex_usage_row(connection: sqlite3.Connection) -> None:
    connection.execute(
        "create table logs (target text not null, timestamp text not null, feedback_log_body text not null)"
    )
    connection.execute(
        "insert into logs (target, timestamp, feedback_log_body) values (?, ?, ?)",
        (
            "codex_core::session::turn",
            "2026-05-01T10:00:00Z",
            json.dumps(
                {
                    "message": "post sampling token usage",
                    "model": "gpt-5.5",
                    "input_tokens": 100,
                    "output_tokens": 50,
                }
            ),
        ),
    )
    connection.commit()
