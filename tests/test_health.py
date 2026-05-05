from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_service_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "silver-usage-report",
    }
