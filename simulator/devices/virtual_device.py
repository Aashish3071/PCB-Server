import random
from typing import Dict, Any
from datetime import datetime, timezone
from devices.models import (
    IdentityState, RuntimeState, SensorState, NetworkState, BufferState, DeviceMode, DeviceEvent
)

class VirtualDevice:
    def __init__(self, device_uid: str, api_key: str, seed: int = 42):
        self.rng = random.Random(seed)
        self.initial_seed = seed
        
        self.identity = IdentityState(device_uid=device_uid, api_key=api_key)
        self.runtime = RuntimeState()
        self.sensors = SensorState()
        self.network = NetworkState()
        self.buffer = BufferState()
        
        self._log_event("Boot", "Virtual device initialized")

    def _log_event(self, event_type: str, description: str):
        self.runtime.events.append(
            DeviceEvent(
                simulation_time=self.runtime.simulation_time,
                event_type=event_type,
                description=description
            )
        )

    def tick(self, delta_seconds: int):
        """Advance the simulation clock by delta_seconds and evolve the device state naturally."""
        if delta_seconds <= 0:
            return
            
        self.runtime.simulation_time += delta_seconds
        self.runtime.uptime_seconds += delta_seconds
        self.runtime.sequence_number += 1
        
        # 1. Energy Model Simulation
        # Drain battery based on time and mode.
        base_drain_per_second = 0.0001
        
        if self.sensors.panel_voltage > 5.0:
            self.runtime.mode = DeviceMode.CHARGING
            self.sensors.charging_current = self.rng.gauss(0.5, 0.05)
            battery_delta = (self.sensors.charging_current * delta_seconds) / 3600.0 * 10  # Arbitrary charge rate
        else:
            self.runtime.mode = DeviceMode.NORMAL
            self.sensors.charging_current = 0.0
            battery_delta = -(base_drain_per_second * delta_seconds)
            
        old_battery = self.sensors.battery_percentage
        self.sensors.battery_percentage += battery_delta
        
        # Enforce boundary
        self.sensors.battery_percentage = max(0.0, min(100.0, self.sensors.battery_percentage))
        
        # Battery voltage roughly linear between 3.0V (0%) and 4.2V (100%)
        self.sensors.battery_voltage = 3.0 + (self.sensors.battery_percentage / 100.0) * 1.2
        
        # Log Low Battery Event
        if old_battery > 20.0 and self.sensors.battery_percentage <= 20.0:
            self._log_event("Low Battery", "Battery fell below 20%")
            self.runtime.mode = DeviceMode.LOW_POWER
            
        # 2. Environmental Drift
        # Temperature drifts continuously, mean reversion to 25.0
        temp_drift = self.rng.gauss(0, 0.1) * (delta_seconds / 60.0)
        self.sensors.temperature += temp_drift
        # Slight mean reversion
        self.sensors.temperature += (25.0 - self.sensors.temperature) * 0.01 * (delta_seconds / 60.0)
        self.sensors.temperature = max(-40.0, min(80.0, self.sensors.temperature))

        # Humidity drifts, mean reversion to 50
        hum_drift = self.rng.gauss(0, 0.5) * (delta_seconds / 60.0)
        self.sensors.humidity += hum_drift
        self.sensors.humidity += (50.0 - self.sensors.humidity) * 0.01 * (delta_seconds / 60.0)
        self.sensors.humidity = max(0.0, min(100.0, self.sensors.humidity))
        
        # 3. Network Drift
        sig_drift = self.rng.gauss(0, 1.0) * (delta_seconds / 60.0)
        self.network.signal_strength += int(sig_drift)
        self.network.signal_strength += int((80 - self.network.signal_strength) * 0.05 * (delta_seconds / 60.0))
        self.network.signal_strength = max(0, min(100, self.network.signal_strength))
        
        # 4. Health Score (Arbitrary calculation for now)
        if self.sensors.battery_percentage < 10.0 or self.sensors.temperature > 60.0:
            self.runtime.health_score = max(0.0, self.runtime.health_score - 1.0 * (delta_seconds / 60.0))
        else:
            self.runtime.health_score = min(100.0, self.runtime.health_score + 1.0 * (delta_seconds / 60.0))

    def get_state(self) -> Dict[str, Any]:
        """Return the complete diagnostic state of the virtual device."""
        return {
            "identity": {
                "device_uid": self.identity.device_uid,
                "hardware_version": self.identity.hardware_version,
                "firmware_version": self.identity.firmware_version,
            },
            "runtime": {
                "boot_count": self.runtime.boot_count,
                "uptime_seconds": self.runtime.uptime_seconds,
                "simulation_time": self.runtime.simulation_time,
                "mode": self.runtime.mode.value,
                "health_score": round(self.runtime.health_score, 2),
                "event_count": len(self.runtime.events)
            },
            "sensors": {
                "temperature": round(self.sensors.temperature, 2),
                "humidity": round(self.sensors.humidity, 2),
                "battery_percentage": round(self.sensors.battery_percentage, 2),
                "battery_voltage": round(self.sensors.battery_voltage, 2),
                "panel_voltage": round(self.sensors.panel_voltage, 2),
                "charging_current": round(self.sensors.charging_current, 2),
                "light_load_status": self.sensors.light_load_status
            },
            "network": {
                "signal_strength": self.network.signal_strength,
                "network_type": self.network.network_type,
                "is_connected": self.network.is_connected
            },
            "buffer": {
                "queue_size": len(self.buffer.telemetry_queue)
            }
        }

    def get_telemetry(self) -> Dict[str, Any]:
        """Generate the payload structure expected by the backend telemetry API (MVP Validation Profile)."""
        return {
            "timestamp": datetime.fromtimestamp(self.runtime.simulation_time, tz=timezone.utc).isoformat(),
            "temperature": round(self.sensors.temperature, 2),
            "humidity": round(self.sensors.humidity, 2)
        }
        
    def reset(self):
        """Simulate a hard hardware reboot."""
        old_boot_count = self.runtime.boot_count
        old_sim_time = self.runtime.simulation_time
        events = self.runtime.events
        
        self.rng = random.Random(self.initial_seed + old_boot_count)  # Change seed slightly on reboot for variance
        
        self.runtime = RuntimeState()
        self.runtime.boot_count = old_boot_count + 1
        self.runtime.simulation_time = old_sim_time # Time does not reset
        self.runtime.events = events
        
        # Re-initialize states that reset on boot
        self.network.is_connected = True
        
        self._log_event("Reboot", "Hardware reset triggered")
