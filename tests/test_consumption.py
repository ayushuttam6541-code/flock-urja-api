import pytest
import httpx
from fastapi.testclient import TestClient

from app.client import UrjaClient
from app.main import app, get_urja_client


@pytest.fixture
def client():
    return TestClient(app)


def test_get_meter_consumption_success(client):
    """Test successful consumption retrieval with numeric string conversion and voltR mapping."""
    portal_energy_response = {
        "data": [
            {
                "timestamp": "23/06/2026 23:30",
                "kwh": "48438.74",
                "kvah": "52313.84",
                "voltR": "226",
            },
            {
                "timestamp": "23/06/2026 23:00",
                "kwh": "48430.10",
                "kvah": "52300.50",
                "voltR": "224.5",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/login" in url:
            return httpx.Response(200, text="Logged in")
        if "/portal/meters/TEST-100/energy" in url:
            return httpx.Response(200, json=portal_energy_response)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters/TEST-100/consumption")
        assert response.status_code == 200
        payload = response.json()
        assert payload["meter_id"] == "TEST-100"
        records = payload["records"]
        assert len(records) == 2

        # Verify numeric conversions and field mapping
        assert records[0] == {
            "timestamp": "23/06/2026 23:30",
            "kwh": 48438.74,
            "kvah": 52313.84,
            "volt_r": 226.0,
        }
        assert records[1] == {
            "timestamp": "23/06/2026 23:00",
            "kwh": 48430.10,
            "kvah": 52300.50,
            "volt_r": 224.5,
        }
    finally:
        app.dependency_overrides.clear()


def test_get_meter_consumption_empty(client):
    """Test consumption endpoint when meter has no energy records."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "/login" in str(request.url):
            return httpx.Response(200, text="Logged in")
        if "/portal/meters/EMPTY-METER/energy" in str(request.url):
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters/EMPTY-METER/consumption")
        assert response.status_code == 200
        payload = response.json()
        assert payload["meter_id"] == "EMPTY-METER"
        assert payload["records"] == []
    finally:
        app.dependency_overrides.clear()


def test_get_meter_consumption_not_found(client):
    """Test consumption endpoint returns 404 when meter does not exist."""
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
        response = client.get("/api/v1/meters/NON_EXISTENT/consumption")
        assert response.status_code == 404
        assert response.json() == {"detail": "Meter not found"}
    finally:
        app.dependency_overrides.clear()


def test_get_meter_consumption_upstream_timeout(client):
    """Test consumption endpoint returns 504 when upstream request times out."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "/login" in str(request.url):
            return httpx.Response(200, text="Logged in")
        raise httpx.ReadTimeout("Connection timed out")

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters/SLOW-METER/consumption")
        assert response.status_code == 504
        assert response.json() == {"detail": "Upstream portal request timed out"}
    finally:
        app.dependency_overrides.clear()
