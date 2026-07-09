from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID
from typing import List, Dict, Any

DeviceStatus = Literal["PROVISIONED", "ONLINE", "OFFLINE", "DISABLED"]

class DeviceBase(BaseModel):
    device_name: str = Field(..., max_length=255)
    device_type: str = Field(default="solar_rms")
    firmware_version: Optional[str] = Field(default=None, max_length=50)
    installation_location: Optional[str] = None
    status: DeviceStatus = Field(default="PROVISIONED")
    upload_interval_seconds: int = Field(
        default=300, ge=30, le=86400,
        description="How often (seconds) the device should upload; returned to the device as next_upload_seconds"
    )

class DeviceCreate(DeviceBase):
    customer_id: UUID

class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    device_type: Optional[str] = Field(default=None)
    firmware_version: Optional[str] = Field(default=None, max_length=50)
    installation_location: Optional[str] = None
    status: Optional[DeviceStatus] = Field(default=None)
    upload_interval_seconds: Optional[int] = Field(default=None, ge=30, le=86400)

class DeviceRead(DeviceBase):
    id: UUID
    device_uid: str
    customer_id: UUID
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class DeviceProvisioned(DeviceRead):
    """Returned only once during provisioning or key rotation."""
    api_key_plaintext: str

class DeviceListRead(DeviceRead):
    """Schema for the device management table."""
    customer_name: Optional[str] = None
    battery_percentage: Optional[float] = None
    signal_strength: Optional[int] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None

class DeviceAnalytics(BaseModel):
    battery_avg: Optional[float] = None
    battery_min: Optional[float] = None
    battery_max: Optional[float] = None
    uptime_seconds: Optional[int] = None
    daily_data_count: int = 0
    battery_trend: List[Dict[str, Any]] = Field(default_factory=list) # { timestamp: str, battery_percentage: float }

class DeviceOverviewResponse(BaseModel):
    device: DeviceListRead
    latest_telemetry: Optional[Any] = None # Will map to TelemetryRead in the route
    analytics: DeviceAnalytics
    recent_alerts: List[Any] = Field(default_factory=list) # Will map to AlertRead

class DeviceHeartbeat(BaseModel):
    online_status: bool
    last_seen: Optional[datetime] = None
    seconds_since_last_packet: Optional[int] = None
    latest_temperature: Optional[float] = None
    latest_humidity: Optional[float] = None
