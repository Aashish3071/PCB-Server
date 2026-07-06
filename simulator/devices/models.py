from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from datetime import datetime

class DeviceMode(Enum):
    NORMAL = "NORMAL"
    CHARGING = "CHARGING"
    LOW_POWER = "LOW_POWER"
    SLEEP = "SLEEP"
    FAULT = "FAULT"

@dataclass
class IdentityState:
    device_uid: str
    api_key: str
    hardware_version: str = "1.0"
    firmware_version: str = "1.0.0"

@dataclass
class DeviceEvent:
    simulation_time: int
    event_type: str
    description: str

@dataclass
class RuntimeState:
    boot_count: int = 1
    uptime_seconds: int = 0
    simulation_time: int = 0
    sequence_number: int = 0
    mode: DeviceMode = DeviceMode.NORMAL
    health_score: float = 100.0
    events: List[DeviceEvent] = field(default_factory=list)

@dataclass
class SensorState:
    temperature: float = 25.0
    humidity: float = 50.0
    battery_percentage: float = 100.0
    battery_voltage: float = 4.2
    panel_voltage: float = 0.0
    charging_current: float = 0.0
    light_load_status: bool = False

@dataclass
class NetworkState:
    signal_strength: int = 80
    network_type: str = "LTE-M"
    is_connected: bool = True

@dataclass
class BufferState:
    telemetry_queue: List[dict] = field(default_factory=list)
