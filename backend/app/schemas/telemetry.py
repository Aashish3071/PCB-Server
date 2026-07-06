from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class TelemetryIngest(BaseModel):
    timestamp: datetime = Field(..., description="Device local timestamp when the reading was taken")
    
    # Readings
    temperature: Optional[float] = Field(None, ge=-50, le=100, description="Temperature in Celsius")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="Humidity percentage")
    panel_voltage: Optional[float] = Field(None, ge=0, le=100, description="Solar panel voltage")
    charging_current: Optional[float] = Field(None, ge=0, le=50, description="Charging current in Amps")
    battery_voltage: Optional[float] = Field(None, ge=0, le=50, description="Battery voltage")
    battery_percentage: Optional[float] = Field(None, ge=0, le=100, description="Battery charge percentage")
    charging_status: Optional[bool] = Field(None, description="Whether the battery is actively charging")
    light_load_status: Optional[bool] = Field(None, description="Whether the light load is currently ON")
    signal_strength: Optional[int] = Field(None, ge=0, le=100, description="Network signal strength percentage or RSSI")
    
    # Metadata / Diagnostics
    hardware_version: Optional[str] = Field(None, max_length=50, description="Hardware revision version")
    boot_count: Optional[int] = Field(None, ge=0, description="Number of times device has booted")
    uptime_seconds: Optional[int] = Field(None, ge=0, description="Time since last boot in seconds")
    network_type: Optional[str] = Field(None, max_length=50, description="Type of network connection (e.g. LTE-M, NB-IoT)")
    firmware_version: Optional[str] = Field(None, max_length=50, description="Current firmware version")

class TelemetryResponse(BaseModel):
    status: str = Field(default="accepted")
    server_time: datetime
    next_upload_seconds: int = Field(default=300, description="Recommended time until next upload")

class TelemetryRead(BaseModel):
    id: UUID
    device_id: UUID
    timestamp: datetime
    server_received_at: datetime
    
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    panel_voltage: Optional[float] = None
    charging_current: Optional[float] = None
    battery_voltage: Optional[float] = None
    battery_percentage: Optional[float] = None
    charging_status: Optional[bool] = None
    light_load_status: Optional[bool] = None
    signal_strength: Optional[int] = None
    
    hardware_version: Optional[str] = None
    boot_count: Optional[int] = None
    uptime_seconds: Optional[int] = None
    network_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class FleetTelemetryRead(TelemetryRead):
    device_name: str
    device_uid: str
    customer_name: Optional[str] = None
