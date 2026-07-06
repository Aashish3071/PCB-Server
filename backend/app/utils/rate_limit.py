"""
Per-device sliding-window rate limiter for the telemetry ingest endpoint.

Scope: in-memory, single-instance. This is intentional for the initial
10-100-device deployment on free-tier hosts (single Fly/Render machine). If the
backend is later scaled horizontally, swap this module for a Redis-backed
implementation — the public surface (RateLimiter.check) can stay the same.

The window and burst limit are driven by the device's own upload_interval_seconds:
- Devices that legitimately upload every N seconds get a burst budget proportional
  to their configured cadence (so we don't have to hand-tune a global cap).
- Anything faster than the floor is 429-ed with a Retry-After header.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Tuple


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    retry_after_seconds: int
    limit: int
    window_seconds: int
    remaining: int


class TelemetryRateLimiter:
    """
    Two-tier per-device rate limit:
      1. Floor: no more than one upload per (interval * FLOOR_MULTIPLIER) seconds.
         Catches obvious runaway devices (config: interval=300s, floor=0.5 → min 150s gap).
      2. Burst window: at most BURST_LIMIT uploads per BURST_WINDOW_SECONDS.
         Catches short bursts even if each request is above the floor.
    """

    def __init__(
        self,
        floor_multiplier: float = 0.5,
        burst_window_seconds: int = 60,
        burst_limit: int = 5,
    ):
        self.floor_multiplier = floor_multiplier
        self.burst_window_seconds = burst_window_seconds
        self.burst_limit = burst_limit
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        # asyncio.Lock is per-loop; async endpoints share the same loop.
        self._lock = asyncio.Lock()

    def _prune(self, times: Deque[float], now: float) -> None:
        cutoff = now - self.burst_window_seconds
        while times and times[0] < cutoff:
            times.popleft()

    async def check(self, device_uid: str, upload_interval_seconds: int) -> LimitDecision:
        floor_gap = upload_interval_seconds * self.floor_multiplier
        async with self._lock:
            now = time.monotonic()
            times = self._hits[device_uid]
            self._prune(times, now)

            # 1. Floor check — reject if the last upload was too recent.
            if times and (now - times[-1]) < floor_gap:
                retry = max(1, int(floor_gap - (now - times[-1])))
                return LimitDecision(False, retry, self.burst_limit, self.burst_window_seconds, 0)

            # 2. Burst check — reject if the window is full.
            if len(times) >= self.burst_limit:
                retry = max(1, int(self.burst_window_seconds - (now - times[0])))
                return LimitDecision(False, retry, self.burst_limit, self.burst_window_seconds, 0)

            times.append(now)
            return LimitDecision(
                True, 0, self.burst_limit, self.burst_window_seconds,
                self.burst_limit - len(times)
            )

    async def snapshot(self) -> Tuple[int, int]:
        """Return (tracked_devices, total_recent_hits). For /diagnostics only."""
        async with self._lock:
            devices = len(self._hits)
            hits = sum(len(q) for q in self._hits.values())
        return devices, hits


telemetry_rate_limiter = TelemetryRateLimiter()
