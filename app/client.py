import os
import re
from typing import Any
import httpx
from dotenv import load_dotenv

from app.models import (
    ConsumptionRecord,
    ConsumptionResponse,
    MeterDetail,
    MeterGeoResponse,
    MeterHierarchy,
    MeterSummary,
)

load_dotenv()

PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech").rstrip("/")
PORTAL_EMAIL = os.getenv("PORTAL_EMAIL", "")
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD", "")


class UrjaClientError(Exception):
    """Base exception for Urja portal errors."""
    pass


class UrjaNotFoundError(UrjaClientError):
    """Raised when a meter is not found."""
    pass


class UrjaTimeoutError(UrjaClientError):
    """Raised when a request times out."""
    pass


class UrjaClient:
    """Client adapter for communicating with the Urja Meter Ops portal."""

    def __init__(
        self,
        base_url: str = PORTAL_BASE_URL,
        email: str = PORTAL_EMAIL,
        password: str = PORTAL_PASSWORD,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.timeout = timeout
        self.logged_in = False

        self.client = httpx.Client(
            base_url=self.base_url,
            follow_redirects=True,
            timeout=self.timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            },
        )

    def login(self) -> None:
        """Authenticate with the portal using form credentials."""
        if not self.email or not self.password:
            raise UrjaClientError("PORTAL_EMAIL and PORTAL_PASSWORD must be configured")

        try:
            # Origin and Referer headers are required by upstream SvelteKit CSRF protection
            response = self.client.post(
                "/login",
                data={"email": self.email, "password": self.password},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": self.base_url,
                    "Referer": f"{self.base_url}/login",
                },
            )
            if response.status_code in (401, 403):
                raise UrjaClientError("Authentication failed: invalid credentials")
            response.raise_for_status()
            self.logged_in = True
        except httpx.TimeoutException as e:
            raise UrjaTimeoutError("Login request timed out") from e
        except UrjaClientError:
            raise
        except Exception as e:
            raise UrjaClientError(f"Login failed: {e}") from e

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        """Execute an authenticated GET request, re-authenticating if session expired."""
        if not self.logged_in:
            self.login()

        try:
            response = self.client.get(path, params=params)

            # Auto-reauthenticate if session expired (redirected to /login or returned 401/403)
            if response.status_code in (401, 403) or str(response.url).endswith("/login"):
                self.logged_in = False
                self.login()
                response = self.client.get(path, params=params)

            if response.status_code == 404:
                raise UrjaNotFoundError("Meter not found")

            response.raise_for_status()
            return response
        except httpx.TimeoutException as e:
            raise UrjaTimeoutError(f"Request to '{path}' timed out") from e
        except UrjaClientError:
            raise
        except Exception as e:
            raise UrjaClientError(f"Upstream request failed: {e}") from e

    def get_meters(self) -> list[MeterSummary]:
        """Fetch all meters across all pages until exhausted."""
        meters: list[MeterSummary] = []
        page = 1
        max_pages = 100

        while page <= max_pages:
            res = self._get("/portal/meters/search", params={"q": "", "page": page})
            data = res.json().get("data", [])
            if not data:
                break

            for item in data:
                meters.append(
                    MeterSummary(
                        meter_id=str(item.get("meterId", "")),
                        serial_no=str(item.get("serialNo", "")),
                        make=str(item.get("make", "")),
                        phase_type=str(item.get("phaseType", "")),
                        install_status=str(item.get("installStatus", "")),
                        dt_code=item.get("dtCode"),
                    )
                )

            total = res.json().get("total")
            if total and len(meters) >= total:
                break

            page += 1

        return meters

    def get_meter_detail(self, meter_id: str) -> MeterDetail:
        """Fetch and parse SvelteKit detail page for a meter."""
        res = self._get(f"/meters/{meter_id}/__data.json", params={"x-sveltekit-invalidated": "001"})
        nodes = res.json().get("nodes", [])

        # SvelteKit returns HTTP 200 with an error node when a meter is missing
        for node in nodes:
            if isinstance(node, dict) and (node.get("type") == "error" or node.get("status") == 404):
                raise UrjaNotFoundError(f"Meter '{meter_id}' not found")

        # Locate the serialized data node array
        data_node = None
        for node in nodes:
            if isinstance(node, dict) and node.get("type") == "data" and isinstance(node.get("data"), list):
                data_node = node["data"]
                break

        if not data_node:
            raise UrjaNotFoundError(f"Meter '{meter_id}' not found")

        # Parse parameter objects: {parameterName: idx, parameterValue: idx}
        params: dict[str, str] = {}
        for item in data_node:
            if isinstance(item, dict) and "parameterName" in item and "parameterValue" in item:
                pn_idx = item["parameterName"]
                pv_idx = item["parameterValue"]
                if isinstance(pn_idx, int) and pn_idx < len(data_node):
                    name = str(data_node[pn_idx])
                    val = str(data_node[pv_idx]) if isinstance(pv_idx, int) and pv_idx < len(data_node) else ""
                    params[name] = val

        # Parse hierarchy dictionary: {Zone: idx, Circle: idx, ...}
        hierarchy_dict = None
        if len(data_node) > 0 and isinstance(data_node[0], dict) and "hierarchy" in data_node[0]:
            h_idx = data_node[0]["hierarchy"]
            if isinstance(h_idx, int) and h_idx < len(data_node) and isinstance(data_node[h_idx], dict):
                hierarchy_dict = data_node[h_idx]

        hierarchy = None
        dt_val = None
        if hierarchy_dict:
            h_data: dict[str, str | None] = {}
            for k, idx in hierarchy_dict.items():
                if isinstance(idx, int) and idx < len(data_node):
                    v = str(data_node[idx])
                    norm_k = k.lower().replace(" ", "").replace("_", "")
                    if "zone" in norm_k:
                        h_data["zone"] = v
                    elif "circle" in norm_k:
                        h_data["circle"] = v
                    elif "subdivision" in norm_k:
                        h_data["subdivision"] = v
                    elif "division" in norm_k:
                        h_data["division"] = v
                    elif "substation" in norm_k:
                        h_data["substation"] = v
                    elif "feeder" in norm_k:
                        h_data["feeder"] = v
                    elif norm_k == "dt":
                        h_data["dt"] = v
                        dt_val = v
            hierarchy = MeterHierarchy(**h_data)

        # Extract DT code e.g. "Malviya Nagar DT 1 (DT-001)" -> "DT-001"
        dt_code = None
        if dt_val:
            match = re.search(r"\(([^)]+)\)", dt_val)
            dt_code = match.group(1).strip() if match else dt_val.strip()

        serial_no = params.get("Serial No", "")
        make = params.get("Make", "")
        if not serial_no and not make:
            raise UrjaNotFoundError(f"Meter '{meter_id}' not found")

        return MeterDetail(
            meter_id=meter_id,
            serial_no=serial_no,
            make=make,
            phase_type=params.get("Phase Type", ""),
            install_status=params.get("Installation Status", ""),
            install_type=params.get("Installation Type"),
            dt_code=dt_code,
            hierarchy=hierarchy,
        )

    def get_meter_consumption(self, meter_id: str) -> ConsumptionResponse:
        """Fetch historical energy records for a meter and convert numeric values."""
        res = self._get(f"/portal/meters/{meter_id}/energy")
        raw_records = res.json().get("data", [])
        records = []

        for r in raw_records:
            try:
                records.append(
                    ConsumptionRecord(
                        timestamp=str(r.get("timestamp", "")),
                        kwh=float(r.get("kwh", 0)),
                        kvah=float(r.get("kvah", 0)),
                        volt_r=float(r.get("voltR", r.get("volt_r", 0))),
                    )
                )
            except (ValueError, TypeError) as e:
                raise UrjaClientError(f"Malformed consumption record: {e}") from e

        return ConsumptionResponse(meter_id=meter_id, records=records)

    def get_meter_geo(self, meter_id: str) -> MeterGeoResponse:
        """Fetch geographical coordinates for a meter."""
        res = self._get(f"/portal/meters/{meter_id}/geo")
        data = res.json().get("data")
        if not isinstance(data, dict):
            raise UrjaNotFoundError(f"Meter '{meter_id}' not found")

        try:
            return MeterGeoResponse(
                meter_id=meter_id,
                latitude=float(data.get("latitude", 0)),
                longitude=float(data.get("longitude", 0)),
            )
        except (ValueError, TypeError) as e:
            raise UrjaClientError(f"Malformed coordinate values: {e}") from e

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
