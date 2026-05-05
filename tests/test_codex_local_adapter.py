import json
import sqlite3
from pathlib import Path

from app.adapters.codex_local import preview_codex_local_usage


def _write_codex_fixture(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "create table logs (target text not null, timestamp text not null, feedback_log_body text not null)"
        )
        connection.executemany(
            "insert into logs (target, timestamp, feedback_log_body) values (?, ?, ?)",
            [
                (
                    "codex_core::session::turn",
                    "2026-05-01T10:00:00Z",
                    json.dumps(
                        {
                            "message": "post sampling token usage",
                            "model": "gpt-5.5",
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "cached_input_tokens": 25,
                            "reasoning_tokens": 10,
                            "total_tokens": 185,
                        }
                    ),
                ),
                (
                    "codex_core::session::turn",
                    "2026-05-01T10:05:00Z",
                    json.dumps(
                        {
                            "message": "post sampling token usage",
                            "model": "gpt-5.5",
                            "input_tokens": 20,
                            "output_tokens": 30,
                            "total_tokens": 50,
                            "approval": "auto-review",
                        }
                    ),
                ),
                (
                    "codex_core::session::turn",
                    "2026-05-01T10:10:00Z",
                    json.dumps({"message": "user prompt", "prompt": "do not read this"}),
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_codex_local_adapter_extracts_only_aggregate_usage_rows():
    db_path = Path(".tmp_codex_logs_extract.sqlite")
    try:
        _write_codex_fixture(db_path)

        rows, warnings = preview_codex_local_usage(db_path)

        assert len(rows) == 1
        assert rows[0].provider == "openai"
        assert rows[0].tool == "codex"
        assert rows[0].source == "codex_local_telemetry"
        assert rows[0].model == "gpt-5.5"
        assert rows[0].input_tokens == 100
        assert rows[0].output_tokens == 50
        assert rows[0].cached_input_tokens == 25
        assert rows[0].reasoning_tokens == 10
        assert rows[0].total_tokens == 185
        assert rows[0].confidence == "medium"
        assert rows[0].evidence is not None
        assert rows[0].evidence.adapter == "codex_local_telemetry"
        assert rows[0].evidence.row_count == 1
        assert warnings[0].code == "codex_internal_usage_excluded"
    finally:
        db_path.unlink(missing_ok=True)


def test_codex_local_adapter_ignores_sensitive_non_usage_rows():
    db_path = Path(".tmp_codex_logs_sensitive.sqlite")
    try:
        _write_codex_fixture(db_path)

        rows, _warnings = preview_codex_local_usage(db_path)

        serialized = json.dumps([row.model_dump(mode="json") for row in rows])
        assert "do not read this" not in serialized
        assert "prompt" not in serialized
    finally:
        db_path.unlink(missing_ok=True)
