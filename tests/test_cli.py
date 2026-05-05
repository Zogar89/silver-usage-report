import json
from pathlib import Path

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
