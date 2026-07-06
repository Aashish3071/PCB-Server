import pytest
from devices.virtual_device import VirtualDevice
from devices.models import DeviceMode

def test_device_initialization():
    device = VirtualDevice(device_uid="TEST-001", api_key="secret", seed=42)
    state = device.get_state()
    
    assert state["identity"]["device_uid"] == "TEST-001"
    assert state["runtime"]["uptime_seconds"] == 0
    assert state["runtime"]["simulation_time"] == 0
    assert state["runtime"]["boot_count"] == 1
    assert state["sensors"]["battery_percentage"] == 100.0

def test_deterministic_drift():
    device1 = VirtualDevice("DEV-1", "key", seed=99)
    device2 = VirtualDevice("DEV-2", "key", seed=99)
    
    # Tick both devices identically
    device1.tick(3600)
    device2.tick(3600)
    
    # Their sensor states should be identical due to the same seed
    t1 = device1.get_telemetry()
    t2 = device2.get_telemetry()
    
    assert t1["temperature"] == t2["temperature"]
    assert t1["battery_percentage"] == t2["battery_percentage"]
    assert t1["signal_strength"] == t2["signal_strength"]

def test_different_seeds_produce_different_drift():
    device1 = VirtualDevice("DEV-1", "key", seed=10)
    device2 = VirtualDevice("DEV-2", "key", seed=20)
    
    device1.tick(3600)
    device2.tick(3600)
    
    t1 = device1.get_telemetry()
    t2 = device2.get_telemetry()
    
    assert t1["temperature"] != t2["temperature"]

def test_battery_drain_and_bounds():
    device = VirtualDevice("DEV-1", "key", seed=42)
    
    # Fast forward many hours
    device.tick(86400 * 30) # 30 days
    
    state = device.get_state()
    # Battery should hit the 0.0 lower bound, not go negative
    assert state["sensors"]["battery_percentage"] == 0.0
    assert state["sensors"]["battery_voltage"] == 3.0

def test_charging_mode():
    device = VirtualDevice("DEV-1", "key", seed=42)
    
    # Force battery down
    device.tick(86400) 
    lowered_battery = device.get_state()["sensors"]["battery_percentage"]
    assert lowered_battery < 100.0
    
    # Emulate solar charging
    device.sensors.panel_voltage = 12.0
    device.tick(3600)
    
    state = device.get_state()
    assert state["runtime"]["mode"] == DeviceMode.CHARGING.value
    assert state["sensors"]["battery_percentage"] > lowered_battery
    assert state["sensors"]["charging_current"] > 0

def test_reset_behavior():
    device = VirtualDevice("DEV-1", "key", seed=42)
    device.tick(3600)
    
    events_before = len(device.runtime.events)
    assert device.runtime.boot_count == 1
    assert device.runtime.uptime_seconds == 3600
    
    device.reset()
    
    state = device.get_state()
    assert state["runtime"]["boot_count"] == 2
    assert state["runtime"]["uptime_seconds"] == 0
    assert state["runtime"]["simulation_time"] == 3600 # Should not reset
    assert state["runtime"]["event_count"] == events_before + 1 # Added Reboot event

def test_boundary_enforcement():
    device = VirtualDevice("DEV-1", "key", seed=42)
    # Manually force invalid values
    device.sensors.temperature = 1000.0
    device.network.signal_strength = -50
    device.sensors.humidity = 200.0
    
    # Tick should pull them back or enforce bounds
    device.tick(1)
    
    state = device.get_state()
    assert state["sensors"]["temperature"] == 80.0
    assert state["network"]["signal_strength"] == 0
    assert state["sensors"]["humidity"] == 100.0
