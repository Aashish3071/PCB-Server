import pytest
import os
import json
import httpx
from unittest.mock import AsyncMock, patch

from devices.fleet import FleetManager
from telemetry_client import TransportClient

@pytest.fixture
def config():
    return {
        "backend": {"url": "http://localhost:8000"},
        "fleet": {"size": 2},
        "telemetry": {"interval_seconds": 300},
        "simulation": {"speed_multiplier": 60},
        "provision": {"auto": True}
    }

@pytest.fixture
def transport():
    return TransportClient(base_url="http://localhost:8000")

@pytest.mark.asyncio
async def test_fleet_initialization_with_auto_provision(config, transport, tmp_path):
    fleet = FleetManager(config, transport)
    fleet.provisioning_file = str(tmp_path / "provisioning.json")
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        
        req = httpx.Request("GET", "http://test")
        # Mock customer GET (no customers)
        mock_get.return_value = httpx.Response(200, json={"items": []}, request=req)
        
        # Mock customer POST
        mock_post_customer_resp = httpx.Response(200, json={"id": "cust-123"}, request=req)
        
        # Mock device POST
        mock_post_device_resp1 = httpx.Response(200, json={"device_uid": "DEV-1", "api_key_plaintext": "key1"}, request=req)
        mock_post_device_resp2 = httpx.Response(200, json={"device_uid": "DEV-2", "api_key_plaintext": "key2"}, request=req)
        
        mock_post.side_effect = [mock_post_customer_resp, mock_post_device_resp1, mock_post_device_resp2]
        
        await fleet.initialize()
        
        assert len(fleet.devices) == 2
        assert fleet.devices[0][0].identity.device_uid == "DEV-1"
        assert fleet.devices[1][0].identity.device_uid == "DEV-2"
        
        # Verify cache file was written
        assert os.path.exists(fleet.provisioning_file)
        with open(fleet.provisioning_file, "r") as f:
            cached = json.load(f)
            assert len(cached) == 2
            assert cached[0]["device_uid"] == "DEV-1"

@pytest.mark.asyncio
async def test_fleet_initialization_from_cache(config, transport, tmp_path):
    fleet = FleetManager(config, transport)
    fleet.provisioning_file = str(tmp_path / "provisioning.json")
    
    # Pre-populate cache
    cached_data = [
        {"device_uid": "DEV-CACHE-1", "api_key": "key1"},
        {"device_uid": "DEV-CACHE-2", "api_key": "key2"}
    ]
    with open(fleet.provisioning_file, "w") as f:
        json.dump(cached_data, f)
        
    # Should not make any network requests since we have enough in cache
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        await fleet.initialize()
        assert not mock_get.called
        
    assert len(fleet.devices) == 2
    assert fleet.devices[0][0].identity.device_uid == "DEV-CACHE-1"

@pytest.mark.asyncio
async def test_fleet_process_device(config, transport):
    fleet = FleetManager(config, transport)
    
    # Initialize manually
    fleet.devices = []
    from devices.virtual_device import VirtualDevice
    from devices.store_and_forward import StoreAndForwardEngine
    
    device = VirtualDevice("TEST-UID", "TEST-KEY")
    buffer = StoreAndForwardEngine()
    fleet.devices.append((device, buffer))
    
    with patch.object(transport, "send_telemetry", new_callable=AsyncMock) as mock_send:
        from telemetry_client import TransportResult
        mock_send.return_value = TransportResult(True, 200, 50.0, False, 300, None, "corr-1")
        
        await fleet._process_device(device, buffer)
        
        # Verify tick progressed time
        assert device.runtime.simulation_time == 300
        
        # Verify buffer size is 0 because batch was acknowledged successfully
        assert buffer.metrics.queue_size == 0
        
        # Verify transport was called
        assert mock_send.called
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["device_uid"] == "TEST-UID"
        assert call_kwargs["payload"]["temperature"] is not None
