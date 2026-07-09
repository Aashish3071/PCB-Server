import asyncio
import json
import os
import httpx
import structlog
from typing import List, Tuple, Dict, Any

from devices.virtual_device import VirtualDevice
from devices.store_and_forward import StoreAndForwardEngine, OverflowPolicy
from telemetry_client import TransportClient

logger = structlog.get_logger()

class FleetManager:
    def __init__(self, config: Dict[str, Any], transport: TransportClient):
        self.config = config
        self.transport = transport
        self.fleet_size = config.get("fleet", {}).get("size", 10)
        self.interval = config.get("telemetry", {}).get("interval_seconds", 300)
        self.speed_multiplier = config.get("simulation", {}).get("speed_multiplier", 1.0)
        self.auto_provision = config.get("provision", {}).get("auto", True)
        
        self.provisioning_file = "state/provisioning.json"
        
        # List of (Device, Buffer)
        self.devices: List[Tuple[VirtualDevice, StoreAndForwardEngine]] = []

    def _load_provisioning_cache(self) -> List[Dict[str, str]]:
        if os.path.exists(self.provisioning_file):
            try:
                with open(self.provisioning_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to load provisioning cache", error=str(e))
        return []

    def _save_provisioning_cache(self, cached: List[Dict[str, str]]):
        os.makedirs(os.path.dirname(self.provisioning_file), exist_ok=True)
        with open(self.provisioning_file, "w") as f:
            json.dump(cached, f, indent=2)

    async def _ensure_customer(self) -> str:
        """Find an existing customer or create a mock one for the simulator."""
        url = f"{self.transport.base_url}/api/v1/customers"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params={"page_size": 1})
            if resp.status_code == 200:
                data = resp.json().get("items", [])
                if data:
                    return data[0]["id"]
            
            # Create a new one
            create_payload = {"company_name": "Simulator Mock Customer"}
            resp = await client.post(url, json=create_payload)
            resp.raise_for_status()
            return resp.json()["id"]

    async def _provision_device(self, customer_id: str, index: int) -> Dict[str, str]:
        """Auto-provision a device via the backend API."""
        url = f"{self.transport.base_url}/api/v1/devices"
        payload = {
            "device_name": f"Simulator Device {index:03d}",
            "device_type": "solar_rms",
            "customer_id": customer_id
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {
                "device_uid": data["device_uid"],
                "api_key": data["api_key_plaintext"]
            }

    async def initialize(self):
        """Provision devices and instantiate the fleet."""
        cached_devices = self._load_provisioning_cache()
        
        needed = self.fleet_size - len(cached_devices)
        if needed > 0 and self.auto_provision:
            logger.info("Auto-provisioning devices", count=needed)
            try:
                customer_id = await self._ensure_customer()
                for i in range(needed):
                    idx = len(cached_devices) + 1
                    credentials = await self._provision_device(customer_id, idx)
                    cached_devices.append(credentials)
                self._save_provisioning_cache(cached_devices)
            except Exception as e:
                logger.error("Auto-provisioning failed", error=str(e))
                raise
        
        # Trim if we decreased fleet size in config
        cached_devices = cached_devices[:self.fleet_size]
        
        # Instantiate Virtual Devices
        for i, creds in enumerate(cached_devices):
            device = VirtualDevice(
                device_uid=creds["device_uid"],
                api_key=creds["api_key"],
                seed=42 + i  # Different seed per device
            )
            buffer = StoreAndForwardEngine(overflow_policy=OverflowPolicy.DROP_OLDEST)
            self.devices.append((device, buffer))
            
        logger.info("Fleet initialized", active_devices=len(self.devices))

    async def _process_device(self, device: VirtualDevice, buffer: StoreAndForwardEngine, tick_seconds: int):
        """Tick device, queue telemetry, send batch. Returns TelemetryResult or None."""
        device.tick(tick_seconds)

        telemetry = device.get_telemetry()
        buffer.enqueue(
            sequence_number=device.runtime.sequence_number,
            payload=telemetry,
            sim_time=device.runtime.simulation_time
        )
        buffer.update_metrics(device.runtime.simulation_time)

        batch = buffer.build_next_batch()
        if not batch:
            return None

        record = batch[0]

        result = await self.transport.send_telemetry(
            device_uid=device.identity.device_uid,
            api_key=device.identity.api_key,
            payload=record.payload
        )
        
        # Improved Console Output for MVP Validation
        print(f"Device: {device.identity.device_uid}")
        print(f"Authenticated: {'YES' if result.status_code != 401 else 'NO'}")
        print(f"Packet #{record.sequence_number}")
        print(f"Temperature: {record.payload.get('temperature', 'N/A')}°C")
        print(f"Humidity: {record.payload.get('humidity', 'N/A')}%")
        print(f"Response: {result.status_code} {'OK' if result.success else 'Error'}")
        print(f"Latency: {int(result.latency_ms)} ms")
        print("-" * 20)

        buffer.acknowledge_batch([record.record_id], result.success)
        return result

    async def _device_loop(self, device: VirtualDevice, buffer: StoreAndForwardEngine):
        """Per-device loop that honors the server's next_upload_seconds control channel."""
        next_upload = self.interval  # initial default until we hear from the server
        while True:
            result = await self._process_device(device, buffer, tick_seconds=next_upload)
            # Server tells the device when to come back. This is the control channel
            # that lets the admin retune fleets from the dashboard with no reflash.
            if result and result.next_upload_seconds:
                next_upload = result.next_upload_seconds
            sleep_duration = next_upload / max(0.1, self.speed_multiplier)
            await asyncio.sleep(sleep_duration)

    async def start(self):
        """Main Fleet Manager execution loop — one asyncio task per virtual device."""
        if not self.devices:
            logger.warning("No devices initialized. Fleet Manager stopping.")
            return

        logger.info("Starting fleet simulation loop",
                    fleet_size=len(self.devices),
                    initial_interval_seconds=self.interval,
                    speed_multiplier=self.speed_multiplier)

        tasks = [asyncio.create_task(self._device_loop(d, b)) for d, b in self.devices]
        await asyncio.gather(*tasks, return_exceptions=True)
