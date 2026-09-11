import pytest
import httpx
from fastapi.testclient import TestClient

from app.client import UrjaClient, UrjaNotFoundError
from app.main import app, get_urja_client


@pytest.fixture
def client():
    return TestClient(app)


def test_root(client):
    """Test root endpoint returns running message."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Urja Meter API is running"}


def test_health_check(client):
    """Test health check returns status: ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_meters_pagination(client):
    """Test multi-page dynamic pagination combining page 1 and page 2 until empty page 3."""
    page_1_data = {
        "data": [
            {
                "meterId": "MTR-001",
                "serialNo": "SN-1001",
                "make": "Schneider",
                "phaseType": "three",
                "installStatus": "Active",
                "dtCode": "DT-101",
            },
            {
                "meterId": "MTR-002",
                "serialNo": "SN-1002",
                "make": "Secure",
                "phaseType": "single",
                "installStatus": "Installed",
                "dtCode": "DT-102",
            },
        ],
        "page": 1,
        "pageSize": 2,
    }
    page_2_data = {
        "data": [
            {
                "meterId": "MTR-003",
                "serialNo": "SN-1003",
                "make": "Genus",
                "phaseType": "single",
                "installStatus": "Active",
                "dtCode": "DT-103",
            }
        ],
        "page": 2,
        "pageSize": 2,
    }
    page_3_data = {
        "data": [],
        "page": 3,
        "pageSize": 2,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/login" in url:
            return httpx.Response(200, text="Logged in")
        if "/portal/meters/search" in url:
            if "page=1" in url:
                return httpx.Response(200, json=page_1_data)
            elif "page=2" in url:
                return httpx.Response(200, json=page_2_data)
            elif "page=3" in url:
                return httpx.Response(200, json=page_3_data)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 3

        # Verify field transformations to snake_case
        assert items[0] == {
            "meter_id": "MTR-001",
            "serial_no": "SN-1001",
            "make": "Schneider",
            "phase_type": "three",
            "install_status": "Active",
            "dt_code": "DT-101",
        }
        assert items[1]["meter_id"] == "MTR-002"
        assert items[2]["meter_id"] == "MTR-003"
    finally:
        app.dependency_overrides.clear()


def test_list_meters_upstream_error(client):
    """Test handling when upstream portal returns a server error."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "/login" in str(request.url):
            return httpx.Response(200, text="Logged in")
        return httpx.Response(500, text="Internal Server Error")

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters")
        assert response.status_code == 502
        assert "Upstream portal service error" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_get_meter_detail_success(client):
    """Test single meter detail with dynamic SvelteKit parsing and hierarchy mapping."""
    # SvelteKit serialized flat structure
    sveltekit_payload = {
        "type": "data",
        "nodes": [
            {"type": "skip"},
            {"type": "skip"},
            {
                "type": "data",
                "data": [
                    {"meterId": 1, "detail": 2, "hierarchy": 21},
                    "CUSTOM-99",
                    {"data": 3},
                    [4, 6, 9, 12, 15, 18],
                    {"parameterName": 5, "parameterValue": 1},
                    "Meter ID",
                    {"parameterName": 7, "parameterValue": 8},
                    "Serial No",
                    "SR-776655",
                    {"parameterName": 10, "parameterValue": 11},
                    "Make",
                    "Landis+Gyr",
                    {"parameterName": 13, "parameterValue": 14},
                    "Phase Type",
                    "three",
                    {"parameterName": 16, "parameterValue": 17},
                    "Installation Status",
                    "Installed",
                    {"parameterName": 19, "parameterValue": 20},
                    "Installation Type",
                    "CT Operated",
                    {
                        "Meter ID": 1,
                        "Installation Status": 17,
                        "Installation Type": 20,
                        "Zone": 22,
                        "Circle": 23,
                        "Division": 24,
                        "Subdivision": 25,
                        "Sub Station": 26,
                        "Feeder": 27,
                        "DT": 28,
                    },
                    "South Zone (SZ-02)",
                    "Urban Circle (UC-05)",
                    "Metro Division (MD-10)",
                    "Subdiv East (SE-01)",
                    "Grid Substation 33kV (GSS-33)",
                    "Industrial Feeder (F-99)",
                    "Industrial Area DT 4 (DT-994)",
                ],
            },
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/login" in url:
            return httpx.Response(200, text="Logged in")
        if "/meters/CUSTOM-99/__data.json" in url:
            return httpx.Response(200, json=sveltekit_payload)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters/CUSTOM-99")
        assert response.status_code == 200
        data = response.json()
        assert data["meter_id"] == "CUSTOM-99"
        assert data["serial_no"] == "SR-776655"
        assert data["make"] == "Landis+Gyr"
        assert data["phase_type"] == "three"
        assert data["install_status"] == "Installed"
        assert data["install_type"] == "CT Operated"
        assert data["dt_code"] == "DT-994"
        assert data["hierarchy"] == {
            "zone": "South Zone (SZ-02)",
            "circle": "Urban Circle (UC-05)",
            "division": "Metro Division (MD-10)",
            "subdivision": "Subdiv East (SE-01)",
            "substation": "Grid Substation 33kV (GSS-33)",
            "feeder": "Industrial Feeder (F-99)",
            "dt": "Industrial Area DT 4 (DT-994)",
        }
    finally:
        app.dependency_overrides.clear()


def test_get_meter_detail_not_found_sveltekit_error_node(client):
    """Test that SvelteKit error node (status 404 inside JSON) returns HTTP 404."""
    sveltekit_error_payload = {
        "type": "data",
        "nodes": [
            {"type": "skip"},
            {"type": "skip"},
            {
                "type": "error",
                "status": 404,
                "error": {"message": "Meter not found"},
            },
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/login" in url:
            return httpx.Response(200, text="Logged in")
        if "/meters/UNKNOWN_METER/__data.json" in url:
            return httpx.Response(200, json=sveltekit_error_payload)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters/UNKNOWN_METER")
        assert response.status_code == 404
        assert response.json() == {"detail": "Meter not found"}
    finally:
        app.dependency_overrides.clear()


def test_get_meter_detail_http_404(client):
    """Test that upstream HTTP 404 returns clean HTTP 404."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "/login" in str(request.url):
            return httpx.Response(200, text="Logged in")
        return httpx.Response(404, text="Not Found")

    mock_transport = httpx.MockTransport(handler)
    mock_client = UrjaClient(email="test@example.com", password="dummy")
    mock_client.client = httpx.Client(
        base_url="https://urja-ops.flockenergy.tech",
        transport=mock_transport,
    )

    app.dependency_overrides[get_urja_client] = lambda: mock_client
    try:
        response = client.get("/api/v1/meters/MISSING_ID")
        assert response.status_code == 404
        assert response.json() == {"detail": "Meter not found"}
    finally:
        app.dependency_overrides.clear()
