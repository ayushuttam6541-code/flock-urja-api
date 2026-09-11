# Urja Portal Protocol & Mapping

This document describes the upstream Urja portal endpoints and how the adapter maps them to our public REST API.

---

## 1. Upstream Endpoints & Public API Mapping

| Public API Endpoint | Upstream Portal Endpoint | Upstream Format | Transformation Performed |
|---|---|---|---|
| `GET /health` | *None (Local)* | N/A | Service liveness indicator |
| `GET /api/v1/meters` | `GET /portal/meters/search?q=&page={n}` | Paginated JSON list (`data`, `page`, `pageSize`) | Iterates all pages until `data: []`, combines records, converts camelCase fields to snake_case |
| `GET /api/v1/meters/{meter_id}` | `GET /meters/{meter_id}/__data.json?x-sveltekit-invalidated=001` | SvelteKit serialized flat array with interned string indices | Resolves interned index references into meter metadata, 7 hierarchy levels, and extracts `dt_code` |
| `GET /api/v1/meters/{meter_id}/consumption` | `GET /portal/meters/{meter_id}/energy` | JSON array with string metrics (`kwh`, `kvah`, `voltR`) | Converts strings to floats, maps `voltR` to `volt_r`, preserves raw timestamps, wraps in `{meter_id, records}` |
| `GET /api/v1/meters/{meter_id}/geo` | `GET /portal/meters/{meter_id}/geo` | JSON object with string coordinates | Converts latitude & longitude strings to floats, returns `{meter_id, latitude, longitude}` |

---

## 2. Upstream Authentication Details

- **Path**: `POST /login`
- **Payload**: `email=<PORTAL_EMAIL>&password=<PORTAL_PASSWORD>` (`application/x-www-form-urlencoded`)
- **Headers**:
  - `User-Agent`: Modern browser identifier.
  - `Origin`: Base URL (required to pass upstream CSRF validation).
  - `Referer`: `<Base URL>/login` (required to pass upstream CSRF validation).
- **Session**: Session cookie returned in `set-cookie` is maintained across subsequent requests.
- **Re-authentication**: If an upstream request redirects to `/login` or returns 401/403, the adapter automatically re-logs in and retries once.

---

## 3. SvelteKit Deserialization

1. **Interned Array**: SvelteKit serializes page data into a flat array (`node["data"]`). Objects store integer indices referencing other elements in the array.
2. **Parameters**: Extracted from objects formatted as `{"parameterName": idx, "parameterValue": idx}`.
3. **Hierarchy**: Extracted from a dictionary mapping hierarchy labels (`Zone`, `Circle`, `Division`, `Subdivision`, `Sub Station`, `Feeder`, `DT`) to value indices.
4. **DT Code**: Extracted from parentheses inside the DT value (e.g. `"Malviya Nagar DT 1 (DT-001)"` -> `"DT-001"`).
5. **Error Nodes**: If a meter does not exist, the HTTP status code is often 200, but a node contains `{"type": "error", "status": 404}`. The adapter detects this and raises a 404.
