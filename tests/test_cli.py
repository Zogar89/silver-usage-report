import json
from pathlib import Path
from unittest.mock import patch

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
