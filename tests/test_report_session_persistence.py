from app.db.session import SessionLocal, reset_database
from app.schemas.usage_report import ReportWarning, UsageReportRow
from app.services.report_sessions import (
    create_report_session,
    delete_report_session_data,
    get_report_session,
    preview_report_session,
    submit_report_session,
)


def _row() -> UsageReportRow:
    return UsageReportRow(
        provider="openai",
        tool="codex",
        source="codex_local_telemetry",
        period_start="2026-05-01T00:00:00Z",
        period_end="2026-05-02T00:00:00Z",
        period_width="1d",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cost_source="unknown",
        confidence="medium",
    )


def test_report_session_preview_persists_across_database_sessions():
    reset_database()

    with SessionLocal() as db:
        session = create_report_session(db, reporter_label="Gabriel")
        preview_report_session(
            db,
            session,
            rows=[_row()],
            warnings=[ReportWarning(code="codex_local_data", message="Codex local telemetry.")],
        )
        session_id = session.id

    with SessionLocal() as db:
        loaded = get_report_session(db, session_id)

        assert loaded is not None
        assert loaded.status == "previewed"
        assert len(loaded.rows) == 1
        assert loaded.rows[0].total_tokens == 150
        assert loaded.warnings[0].code == "codex_local_data"


def test_delete_report_session_data_persists_empty_report():
    reset_database()

    with SessionLocal() as db:
        session = create_report_session(db)
        preview_report_session(db, session, rows=[_row()], warnings=[])
        delete_report_session_data(db, session)
        session_id = session.id

    with SessionLocal() as db:
        loaded = get_report_session(db, session_id)

        assert loaded is not None
        assert loaded.status == "deleted"
        assert loaded.rows == []
        assert loaded.warnings == []
