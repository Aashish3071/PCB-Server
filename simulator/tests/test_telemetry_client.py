import pytest
import httpx
from unittest.mock import AsyncMock, patch
from telemetry_client import TransportClient, TransportResult

@pytest.fixture
def client():
    return TransportClient(base_url="http://localhost:8000")

@pytest.mark.asyncio
async def test_successful_telemetry_upload(client):
    mock_response = httpx.Response(200, json={"next_upload_seconds": 600})
    
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        result = await client.send_telemetry("UID-1", "KEY", {"temp": 25.0})
        
        assert result.success is True
        assert result.status_code == 200
        assert result.next_upload_seconds == 600
        assert result.should_retry is False
        assert result.correlation_id is not None
        
        # Check metrics
        assert client.metrics.requests_sent == 1
        assert client.metrics.successful_requests == 1
        assert client.metrics.failed_requests == 0
        
        # Check headers
        call_kwargs = mock_request.call_args.kwargs
        assert call_kwargs["headers"]["X-Device-UID"] == "UID-1"
        assert call_kwargs["headers"]["X-API-Key"] == "KEY"
        assert "X-Request-ID" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-Telemetry-Version"] == "1"

@pytest.mark.asyncio
async def test_authentication_failure_no_retry(client):
    mock_response = httpx.Response(401)
    
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        result = await client.send_telemetry("UID-1", "BADKEY", {})
        
        assert result.success is False
        assert result.status_code == 401
        assert result.should_retry is False
        
        assert client.metrics.requests_sent == 1
        assert client.metrics.failed_requests == 1
        assert client.metrics.authentication_failures == 1
        assert client.metrics.retries == 0

@pytest.mark.asyncio
async def test_transient_failure_retries(client):
    # Mock sequence: 500 (transient), 502 (transient), 200 (success)
    responses = [
        httpx.Response(500),
        httpx.Response(502),
        httpx.Response(200, json={"next_upload_seconds": 300})
    ]
    
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = responses
        
        # Reduce backoff time for tests by patching asyncio.sleep
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.send_telemetry("UID-1", "KEY", {})
            
        assert result.success is True
        assert client.metrics.requests_sent == 3
        assert client.metrics.retries == 2
        assert client.metrics.successful_requests == 1
        assert client.metrics.failed_requests == 2

@pytest.mark.asyncio
async def test_network_timeout_retries(client):
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = httpx.ReadTimeout("Timeout")
        
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.send_telemetry("UID-1", "KEY", {})
            
        assert result.success is False
        assert result.should_retry is True # It was a retriable error, but we exhausted retries
        assert result.error_message == "Timeout"
        
        # Max retries is 3, so 1 initial request + 3 retries = 4 sent
        assert client.metrics.requests_sent == 4
        assert client.metrics.retries == 3
