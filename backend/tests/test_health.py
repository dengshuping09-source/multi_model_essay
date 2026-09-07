from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.db.session import DatabaseUnavailableError
from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "essay-evaluation-api",
    }


def test_database_health_check(monkeypatch) -> None:
    check = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.routes.health.check_database_connection", check)

    response = client.get("/api/health/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "postgresql"}
    check.assert_awaited_once()


def test_database_health_check_when_unavailable(monkeypatch) -> None:
    check = AsyncMock(side_effect=DatabaseUnavailableError("offline"))
    monkeypatch.setattr("app.api.routes.health.check_database_connection", check)

    response = client.get("/api/health/database")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
