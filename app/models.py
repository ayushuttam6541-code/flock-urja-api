from pydantic import BaseModel


class MeterSummary(BaseModel):
    meter_id: str
    serial_no: str
    make: str
    phase_type: str
    install_status: str
    dt_code: str | None = None


class MeterHierarchy(BaseModel):
    zone: str | None = None
    circle: str | None = None
    division: str | None = None
    subdivision: str | None = None
    substation: str | None = None
    feeder: str | None = None
    dt: str | None = None


class MeterDetail(BaseModel):
    meter_id: str
    serial_no: str
    make: str
    phase_type: str
    install_status: str
    install_type: str | None = None
    dt_code: str | None = None
    hierarchy: MeterHierarchy | None = None


class ConsumptionRecord(BaseModel):
    timestamp: str
    kwh: float
    kvah: float
    volt_r: float


class ConsumptionResponse(BaseModel):
    meter_id: str
    records: list[ConsumptionRecord] = []


class MeterGeoResponse(BaseModel):
    meter_id: str
    latitude: float
    longitude: float
