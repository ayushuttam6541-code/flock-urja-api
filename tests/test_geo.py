import pytest
import httpx
from fastapi.testclient import TestClient

from app.client import UrjaClient
from app.main import app, get_urja_client


@pytest.fixture
def client():
    return TestClient(app)


def test_get_meter_geo_success(client):
    """Test successful geo coordinate retrieval and float conversion."""
    portal_geo_response = {
        "data": {
            "latitude": "26.938961002479868",
            "longitude": "75.83095696146852",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/login" in url:
            return httpx.Response(200, text="Logged in")
        if "/portal/meters/GEO-001/geo" in url:
            return httpx.Response(200, json=portal_geo_response)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters/GEO-001/geo")
        assert response.status_code == 200
        data = response.json()
        assert data["meter_id"] == "GEO-001"
        assert isinstance(data["latitude"], float)
        assert isinstance(data["longitude"], float)
        assert data["latitude"] == pytest.approx(26.938961002479868)
        assert data["longitude"] == pytest.approx(75.83095696146852)
    finally:
        app.dependency_overrides.clear()


def test_get_meter_geo_not_found(client):
    """Test geo endpoint returns 404 when meter does not exist."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "/login" in str(request.url):
            return httpx.Response(200, text="Logged in")
        return httpx.Response(404, json={"error": "not_found", "message": "Meter not found"})

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters/NON-EXISTENT/geo")
        assert response.status_code == 404
        assert response.json() == {"detail": "Meter not found"}
    finally:
        app.dependency_overrides.clear()


def test_get_meter_geo_malformed_data(client):
    """Test geo endpoint returns 502 when coordinate string is not a valid float."""
    portal_malformed_response = {
        "data": {
            "latitude": "not-a-number",
            "longitude": "not-a-number",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "/login" in str(request.url):
            return httpx.Response(200, text="Logged in")
        if "/portal/meters/BAD-GEO/geo" in str(request.url):
            return httpx.Response(200, json=portal_malformed_response)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters/BAD-GEO/geo")
        assert response.status_code == 502
        assert "Upstream portal service error" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
