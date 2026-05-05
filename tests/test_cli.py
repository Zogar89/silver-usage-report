import json
import sqlite3
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
