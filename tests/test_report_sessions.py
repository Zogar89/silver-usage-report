from datetime import UTC, datetime

from app.db.session import SessionLocal, reset_database
from app.services.report_sessions import create_report_session, get_report_session


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
