from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.health import CheckStatus, readiness_checks
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_no_toca_dependencias(client: TestClient) -> None:
    def fail() -> dict[str, CheckStatus]:
        raise AssertionError("/health no debe ejecutar los chequeos")

    app.dependency_overrides[readiness_checks] = fail
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok(client: TestClient) -> None:
    app.dependency_overrides[readiness_checks] = lambda: {"database": "ok", "storage": "ok"}
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize("failing", ["database", "storage"])
def test_ready_responde_503_si_falla_una_dependencia(client: TestClient, failing: str) -> None:
    checks = {"database": "ok", "storage": "ok", failing: "error"}
    app.dependency_overrides[readiness_checks] = lambda: checks
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": checks}
