import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.codex_local import preview_codex_local_usage, preview_codex_sessions_usage


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


def test_codex_local_adapter_supports_epoch_ts_schema_without_timestamp_column():
    db_path = Path(".tmp_codex_logs_ts_schema.sqlite")
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "create table logs (target text not null, ts integer not null, ts_nanos integer, feedback_log_body text not null)"
        )
        connection.execute(
            "insert into logs (target, ts, ts_nanos, feedback_log_body) values (?, ?, ?, ?)",
            (
                "codex_core::session::turn",
                1777094516,
                808800,
                json.dumps(
                    {
                        "message": "post sampling token usage",
                        "model": "gpt-5.5",
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_tokens": 150,
                    }
                ),
            ),
        )
        connection.commit()
        connection.close()

        rows, warnings = preview_codex_local_usage(db_path)

        assert len(rows) == 1
        assert rows[0].period_start.isoformat() == "2026-04-25T05:21:56.000809+00:00"
        assert rows[0].total_tokens == 150
        assert warnings == []
    finally:
        connection.close()
        db_path.unlink(missing_ok=True)


def test_codex_local_adapter_prefers_state_rollups_next_to_logs_db():
    tmp_dir = Path(".tmp_codex_state_rollup")
    tmp_dir.mkdir(exist_ok=True)
    logs_db_path = tmp_dir / "logs_2.sqlite"
    state_db_path = tmp_dir / "state_5.sqlite"
    logs_connection = sqlite3.connect(logs_db_path)
    state_connection = sqlite3.connect(state_db_path)
    try:
        logs_connection.execute(
            "create table logs (target text not null, ts integer not null, feedback_log_body text not null)"
        )
        logs_connection.commit()
        logs_connection.close()

        state_connection.execute(
            """
            create table threads (
                id text not null,
                created_at integer not null,
                updated_at integer not null,
                created_at_ms integer,
                updated_at_ms integer,
                model_provider text,
                model text,
                tokens_used integer
            )
            """
        )
        state_connection.execute(
            """
            insert into threads (
                id, created_at, updated_at, created_at_ms, updated_at_ms, model_provider, model, tokens_used
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "thread_123",
                1777094516,
                1777094526,
                1777094516808,
                1777094526123,
                "openai",
                "gpt-5.5",
                150,
            ),
        )
        state_connection.commit()
        state_connection.close()

        rows, warnings = preview_codex_local_usage(logs_db_path)

        assert len(rows) == 1
        assert rows[0].model == "gpt-5.5"
        assert rows[0].total_tokens == 150
        assert rows[0].evidence is not None
        assert rows[0].evidence.query_fingerprint == "codex_state_threads_tokens_used_v1"
        assert warnings == []
    finally:
        logs_connection.close()
        state_connection.close()
        logs_db_path.unlink(missing_ok=True)
        state_db_path.unlink(missing_ok=True)
        tmp_dir.rmdir()


def test_codex_sessions_adapter_extracts_usage_from_rollout_jsonl():
    sessions_dir = Path(".tmp_codex_sessions")
    rollout_dir = sessions_dir / "2026" / "04" / "25"
    rollout_dir.mkdir(parents=True, exist_ok=True)
    rollout_path = rollout_dir / "rollout-2026-04-25T05-21-56-thread.jsonl"
    try:
        rollout_path.write_text(
            "\n".join(
                [
                    json.dumps({"type": "user_message", "text": "do not upload this"}),
                    json.dumps(
                        {
                            "timestamp": "2026-04-25T05:21:55Z",
                            "type": "event_msg",
                            "payload": {
                                "type": "session_meta",
                                "model": "gpt-5.5",
                                "model_provider": "openai",
                                "model_context_window": 258400,
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "timestamp": "2026-04-25T05:21:56Z",
                            "type": "event_msg",
                            "payload": {
                                "type": "token_count",
                                "info": {
                                    "model_context_window": 258400,
                                    "total_token_usage": {
                                        "input_tokens": 100,
                                        "cached_input_tokens": 25,
                                        "output_tokens": 50,
                                        "reasoning_output_tokens": 10,
                                        "total_tokens": 185,
                                    },
                                    "last_token_usage": {
                                        "input_tokens": 100,
                                        "cached_input_tokens": 25,
                                        "output_tokens": 50,
                                        "reasoning_output_tokens": 10,
                                        "total_tokens": 185,
                                    },
                                },
                                "rate_limits": {
                                    "plan_type": "pro",
                                    "primary": {"used_percent": 12.5},
                                    "secondary": {"used_percent": 3.5},
                                },
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )

        rows, warnings = preview_codex_sessions_usage(sessions_dir)

        assert len(rows) == 1
        assert rows[0].input_tokens == 100
        assert rows[0].cached_input_tokens == 25
        assert rows[0].output_tokens == 50
        assert rows[0].reasoning_tokens == 10
        assert rows[0].total_tokens == 185
        assert rows[0].model == "gpt-5.5"
        assert rows[0].evidence is not None
        assert rows[0].evidence.query_fingerprint == "codex_sessions_token_count_total_usage_v1"
        assert rows[0].evidence.model_context_window == 258400
        assert rows[0].evidence.plan_type == "pro"
        assert rows[0].evidence.rate_limit_primary_used_percent == 12.5
        assert rows[0].evidence.rate_limit_secondary_used_percent == 3.5
        assert warnings == []
        serialized = json.dumps([row.model_dump(mode="json") for row in rows])
        assert "do not upload this" not in serialized
    finally:
        rollout_path.unlink(missing_ok=True)
        rollout_dir.rmdir()
        (sessions_dir / "2026" / "04").rmdir()
        (sessions_dir / "2026").rmdir()
        sessions_dir.rmdir()


def test_codex_sessions_adapter_can_aggregate_recent_usage_by_day_and_model():
    sessions_dir = Path(".tmp_codex_sessions_aggregate")
    first_dir = sessions_dir / "2026" / "05" / "01"
    second_dir = sessions_dir / "2026" / "05" / "02"
    first_dir.mkdir(parents=True, exist_ok=True)
    second_dir.mkdir(parents=True, exist_ok=True)
    first_path = first_dir / "rollout-2026-05-01T10-00-00-first.jsonl"
    second_path = first_dir / "rollout-2026-05-01T11-00-00-second.jsonl"
    old_path = second_dir / "rollout-2026-05-02T10-00-00-old.jsonl"
    try:
        first_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-05-01T10:00:00Z",
                    "model": "gpt-5.5",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 100,
                                "cached_input_tokens": 20,
                                "output_tokens": 50,
                                "reasoning_output_tokens": 5,
                                "total_tokens": 175,
                            }
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        second_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-05-01T11:00:00Z",
                    "model": "gpt-5.5",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 200,
                                "output_tokens": 25,
                                "total_tokens": 225,
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
                    "timestamp": "2026-04-01T10:00:00Z",
                    "model": "gpt-5.5",
                    "payload": {
                        "type": "token_count",
                        "info": {"total_token_usage": {"input_tokens": 999, "total_tokens": 999}},
                    },
                }
            ),
            encoding="utf-8",
        )

        rows, warnings = preview_codex_sessions_usage(
            sessions_dir,
            since=datetime(2026, 4, 15, tzinfo=UTC),
            aggregate=True,
        )

        assert warnings == []
        assert len(rows) == 1
        assert rows[0].period_width == "1d"
        assert rows[0].period_start.isoformat() == "2026-05-01T00:00:00+00:00"
        assert rows[0].period_end.isoformat() == "2026-05-02T00:00:00+00:00"
        assert rows[0].model == "gpt-5.5"
        assert rows[0].request_count == 2
        assert rows[0].input_tokens == 300
        assert rows[0].cached_input_tokens == 20
        assert rows[0].output_tokens == 75
        assert rows[0].reasoning_tokens == 5
        assert rows[0].total_tokens == 400
        assert rows[0].evidence is not None
        assert rows[0].evidence.row_count == 2
        assert rows[0].evidence.query_fingerprint == "codex_sessions_daily_model_usage_v1"
    finally:
        first_path.unlink(missing_ok=True)
        second_path.unlink(missing_ok=True)
        old_path.unlink(missing_ok=True)
        first_dir.rmdir()
        second_dir.rmdir()
        (sessions_dir / "2026" / "05").rmdir()
        (sessions_dir / "2026").rmdir()
        sessions_dir.rmdir()
