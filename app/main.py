from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status

from app.client import UrjaClient, UrjaClientError, UrjaNotFoundError, UrjaTimeoutError
from app.models import (
    ConsumptionResponse,
    MeterDetail,
    MeterGeoResponse,
    MeterSummary,
)

_client = UrjaClient()


def get_client() -> UrjaClient:
    """Provides the UrjaClient instance (overridable in tests)."""
    return _client


# Backward-compatible alias for existing test imports
get_urja_client = get_client


def handle_error(e: Exception) -> HTTPException:
    """Maps client exceptions to appropriate HTTP error responses."""
    if isinstance(e, UrjaNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found")
    if isinstance(e, UrjaTimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream portal request timed out",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Upstream portal service error",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    _client.close()


app = FastAPI(
    title="Urja Meter Ops API",
    description="Clean REST API adapter for the Urja Meter Ops portal",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["System"])
def root() -> dict:
    return {"message": "Urja Meter API is running"}


@app.get("/health", tags=["System"])
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/meters", response_model=list[MeterSummary], tags=["Meters"])
def list_meters(client: UrjaClient = Depends(get_client)) -> list[MeterSummary]:
    try:
        return client.get_meters()
    except Exception as e:
        raise handle_error(e)


@app.get("/api/v1/meters/{meter_id}", response_model=MeterDetail, tags=["Meters"])
def get_meter_detail(meter_id: str, client: UrjaClient = Depends(get_client)) -> MeterDetail:
    meter_id = meter_id.strip()
    if not meter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found")
    try:
        return client.get_meter_detail(meter_id)
    except Exception as e:
        raise handle_error(e)


@app.get("/api/v1/meters/{meter_id}/consumption", response_model=ConsumptionResponse, tags=["Meters"])
def get_meter_consumption(meter_id: str, client: UrjaClient = Depends(get_client)) -> ConsumptionResponse:
    meter_id = meter_id.strip()
    if not meter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found")
    try:
        return client.get_meter_consumption(meter_id)
    except Exception as e:
        raise handle_error(e)


@app.get("/api/v1/meters/{meter_id}/geo", response_model=MeterGeoResponse, tags=["Meters"])
def get_meter_geo(meter_id: str, client: UrjaClient = Depends(get_client)) -> MeterGeoResponse:
    meter_id = meter_id.strip()
    if not meter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found")
    try:
        return client.get_meter_geo(meter_id)
    except Exception as e:
        raise handle_error(e)