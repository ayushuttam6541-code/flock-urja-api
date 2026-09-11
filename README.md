# Urja Meter Ops REST API

A clean, production-style REST API service built with **Python 3.10+**, **FastAPI**, and **httpx**.

This service acts as an **API Adapter** in front of the existing **Urja Meter Ops portal** (`https://urja-ops.flockenergy.tech`). It transforms legacy web session authentication, SvelteKit serialized internal data, and camelCase fields into clean, standardized, snake_case REST APIs.

---

Live URL: https://flock-urja-api.onrender.com

## 1. Architecture

```
Client / Application
        |
        v
FastAPI Service (app/main.py)
        |
        v
UrjaClient Adapter (app/client.py)
        |
        v
Urja Meter Ops Portal (https://urja-ops.flockenergy.tech)
```

- **Stateless & Simple**: No database, Redis, Celery, or frontend.
- **Direct & Modular**: Core implementation consists of just 3 files:
  - `app/main.py`: FastAPI app and endpoint definitions.
  - `app/client.py`: Upstream portal HTTP client, session management, dynamic pagination, and SvelteKit parser.
  - `app/models.py`: Clean Pydantic response models.

---

## 2. API Endpoints

| Method | Endpoint | Description | Sample Output |
|---|---|---|---|
| `GET` | `/health` | Service health status | `{"status": "ok"}` |
| `GET` | `/api/v1/meters` | List all meters (dynamically paginated) | `[{"meter_id": "J100000", ...}]` |
| `GET` | `/api/v1/meters/{meter_id}` | Meter details & 7-level electrical hierarchy | `{"meter_id": "...", "hierarchy": {...}}` |
| `GET` | `/api/v1/meters/{meter_id}/consumption` | Historical energy telemetry (`kwh`, `kvah`, `volt_r`) | `{"meter_id": "...", "records": [...]}` |
| `GET` | `/api/v1/meters/{meter_id}/geo` | Latitude & longitude coordinates | `{"meter_id": "...", "latitude": 26.93, ...}` |

Interactive docs:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

---

## 3. Setup & Running Locally

### 1. Prerequisites
- Python 3.10+
- Virtual environment (`venv`)

### 2. Installation
```bash
# Clone & enter directory
git clone <repo-url>
cd flock-urja-api

# Create & activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate     

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` and fill in credentials:
```bash
cp .env.example .env
```
Contents of `.env`:
```env
PORTAL_BASE_URL=https://urja-ops.flockenergy.tech
PORTAL_EMAIL=your_email@example.com
PORTAL_PASSWORD=your_password
```

### 4. Run Server
```bash
uvicorn app.main:app --reload
```
The API is available at `http://127.0.0.1:8000`.

---

## 4. Running Tests

Unit tests are fully mocked using `httpx.MockTransport` and require **no live credentials or network access**.

```bash
pytest -v
```

All 13 tests verify:
- Health endpoint status
- Dynamic multi-page pagination combining records until the last empty page
- SvelteKit interned array parsing & hierarchy mapping
- Numeric string conversion to floats (`kwh`, `kvah`, `volt_r`)
- Missing meter 404 handling (including SvelteKit inline error nodes)
- Upstream network errors and timeouts (502 / 504)

---

## 5. Important Implementation Details

1. **Dynamic Pagination (No Hardcoding)**:
   - The portal returns 20 meters per page.
   - `get_meters()` fetches `page=1, 2, 3...` dynamically until an empty list is returned.
   - Total meters and page counts are never hardcoded.
2. **SvelteKit Interned Data Deserialization**:
   - `/meters/{meter_id}/__data.json` returns SvelteKit serialized flat arrays.
   - Strings and hierarchy mappings are resolved from referenced indices.
   - Detects inline SvelteKit 404 error nodes (`{"type": "error", "status": 404}`).
3. **Telemetry Normalization**:
   - Numeric strings (`kwh`, `kvah`, `voltR`) are converted to floats.
   - Portal camelCase `voltR` is mapped to `volt_r`.
   - Timestamps are preserved as provided without inventing timezone data.
4. **Session Resilience**:
   - Upstream CSRF check requires `Origin` and `Referer` headers on `/login`.
   - Cookies are persisted and automatically renewed if a session expires.


  ## Author
  Ayush Raj
