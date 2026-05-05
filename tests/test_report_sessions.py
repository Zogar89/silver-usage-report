from datetime import UTC, datetime

from app.db.session import SessionLocal, reset_database
from app.schemas.usage_report import UsageReportRow
from app.services.report_sessions import ReportSession, create_report_session, get_report_session, summarize_report_session


def test_create_report_session_returns_private_session_details():
    reset_database()

    with SessionLocal() as db:
        session = create_report_session(db, reporter_label="Gabriel")

    assert session.id
    assert len(session.public_code) == 6
    assert session.private_token
    assert session.reporter_label == "Gabriel"
    assert session.status == "draft"
    assert session.expires_at > datetime.now(UTC)


def test_get_report_session_returns_created_session():
    reset_database()

    with SessionLocal() as db:
        session = create_report_session(db)
        loaded = get_report_session(db, session.id)

    assert loaded is not None
    assert loaded.id == session.id
    assert loaded.public_code == session.public_code
    assert loaded.private_token is None


def test_summarize_report_session_groups_usage_by_day():
    session = ReportSession(
        id="session_123",
        public_code="ABC123",
        expires_at=datetime(2026, 5, 6, tzinfo=UTC),
        rows=[
            UsageReportRow(
                provider="openai",
                tool="codex",
                source="codex_local_telemetry",
                period_start="2026-05-01T00:00:00Z",
                period_end="2026-05-02T00:00:00Z",
                period_width="1d",
                request_count=2,
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost_source="unknown",
                confidence="medium",
            ),
            UsageReportRow(
                provider="openai",
                tool="codex",
                source="codex_local_telemetry",
                period_start="2026-05-01T00:00:00Z",
                period_end="2026-05-02T00:00:00Z",
                period_width="1d",
                request_count=1,
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                cost_source="unknown",
                confidence="medium",
            ),
        ],
    )

    summary = summarize_report_session(session)

    assert len(summary.daily_usage) == 1
    assert summary.daily_usage[0].day == "2026-05-01"
    assert summary.daily_usage[0].request_count == 3
    assert summary.daily_usage[0].input_tokens == 120
    assert summary.daily_usage[0].output_tokens == 60
    assert summary.daily_usage[0].total_tokens == 180
