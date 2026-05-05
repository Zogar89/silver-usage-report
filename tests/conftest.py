import pytest
import json
import time

from fastapi.testclient import TestClient

from app.api.usage_report import _body_signature
from app.db.session import reset_database


@pytest.fixture(autouse=True)
def clean_database():
    reset_database()
    yield


def signed_post(client: TestClient, url: str, token: str, payload: dict) -> object:
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    return client.post(
        url,
        params={"token": token},
        content=body,
        headers={
            "content-type": "application/json",
            "x-silver-timestamp": timestamp,
            "x-silver-signature": _body_signature(token, timestamp, body),
        },
    )
