from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DashboardSummary(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    active_alerts: int
    total_customers: int
    last_telemetry_timestamp: Optional[datetime] = None
