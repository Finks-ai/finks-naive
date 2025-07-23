"""Basic health check tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


def test_root_endpoint(client: TestClient) -> None:
    """Test the root endpoint returns expected response."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["version"] == "0.2.0"


def test_health_endpoint(client: TestClient) -> None:
    """Test the health endpoint."""
    response = client.get("/health")
    # Health check might fail if DB is not available, but endpoint should exist
    assert response.status_code in [200, 503]
    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        assert "database" in data
