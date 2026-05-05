import pytest

from app.db.session import reset_database


@pytest.fixture(autouse=True)
def clean_database():
    reset_database()
    yield
