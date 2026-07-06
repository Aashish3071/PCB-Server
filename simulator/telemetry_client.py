import asyncio
import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import httpx
import structlog

logger = structlog.get_logger()

@dataclass
class TransportResult:
    success: bool
    status_code: Optional[int]
    latency_ms: float
    should_retry: bool
    next_upload_seconds: Optional[int]
    error_message: Optional[str]
    correlation_id: str

@dataclass
class TransportMetrics:
    requests_sent: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retries: int = 0
    authentication_failures: int = 0
    total_latency_ms: float = 0.0

    @property
    def average_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

class TransportClient:
    """
    Foundation of the device transport layer.
    Handles resilient communication with the backend.
    """
    def __init__(self, base_url: str, verify_ssl: bool = True, telemetry_version: int = 1):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.telemetry_version = telemetry_version
        self.metrics = TransportMetrics()
        
        # We hold an active async client for connection pooling.
        self._client = httpx.AsyncClient(verify=self.verify_ssl)

    async def close(self):
        await self._client.aclose()

    def _should_retry(self, status_code: Optional[int], exc: Optional[Exception]) -> bool:
        """Determine if a failure is transient and should be retried."""
        if exc is not None:
            # Network errors, timeouts, etc.
            return True
            
        if status_code in (429, 500, 502, 503, 504):
            return True
            
        return False

    async def _execute_with_retries(
        self, 
        method: str, 
        endpoint: str, 
        headers: Dict[str, str], 
        json_payload: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> TransportResult:
        correlation_id = str(uuid.uuid4())
        headers["X-Request-ID"] = correlation_id
        headers["X-Telemetry-Version"] = str(self.telemetry_version)
        
        url = f"{self.base_url}{endpoint}"
        
        attempt = 0
        backoff = 1.0
        
        while attempt <= max_retries:
            self.metrics.requests_sent += 1
            start_time = time.monotonic()
            
            exc: Optional[Exception] = None
            response: Optional[httpx.Response] = None
            status_code: Optional[int] = None
            
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_payload,
                    timeout=10.0
                )
                status_code = response.status_code
            except httpx.RequestError as e:
                exc = e
                
            latency_ms = (time.monotonic() - start_time) * 1000
            
            # Determine success
            success = status_code is not None and 200 <= status_code < 300
            should_retry = not success and self._should_retry(status_code, exc)
            
            # Update metrics
            if success:
                self.metrics.successful_requests += 1
                self.metrics.total_latency_ms += latency_ms
                
                # Try parsing backend response
                next_upload_seconds = None
                if response:
                    try:
                        data = response.json()
                        next_upload_seconds = data.get("next_upload_seconds")
                    except Exception:
                        pass
                
                return TransportResult(
                    success=True,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    should_retry=False,
                    next_upload_seconds=next_upload_seconds,
                    error_message=None,
                    correlation_id=correlation_id
                )
            
            # Record specific failure metrics
            self.metrics.failed_requests += 1
            if status_code == 401 or status_code == 403:
                self.metrics.authentication_failures += 1

            # Prepare error message
            error_msg = str(exc) if exc else f"HTTP {status_code}"
            
            if should_retry and attempt < max_retries:
                attempt += 1
                self.metrics.retries += 1
                logger.warning(
                    "Transport transient failure, retrying",
                    endpoint=endpoint,
                    attempt=attempt,
                    correlation_id=correlation_id,
                    error=error_msg,
                    backoff_seconds=backoff
                )
                await asyncio.sleep(backoff)
                backoff *= 2.0  # Exponential backoff
                continue
            
            # Exhausted retries or non-retriable error
            logger.error(
                "Transport failure",
                endpoint=endpoint,
                correlation_id=correlation_id,
                error=error_msg,
                status_code=status_code,
                should_retry=should_retry
            )
            return TransportResult(
                success=False,
                status_code=status_code,
                latency_ms=latency_ms,
                should_retry=should_retry,
                next_upload_seconds=None,
                error_message=error_msg,
                correlation_id=correlation_id
            )

        # Should never reach here
        return TransportResult(False, None, 0.0, False, None, "Unknown error", correlation_id)

    async def send_telemetry(self, device_uid: str, api_key: str, payload: Dict[str, Any]) -> TransportResult:
        """Send telemetry payload to the backend API."""
        headers = {
            "X-Device-UID": device_uid,
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        return await self._execute_with_retries(
            method="POST",
            endpoint="/api/v1/telemetry",
            headers=headers,
            json_payload=payload
        )
