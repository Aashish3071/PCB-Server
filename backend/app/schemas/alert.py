from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class AlertBase(BaseModel):
    alert_type: str
    severity: str
    message: str
    metadata_: Optional[Dict[str, Any]] = None

class AlertCreate(AlertBase):
    device_id: UUID

class AlertUpdate(BaseModel):
    is_resolved: bool
    resolved_at: Optional[datetime] = None

class AlertRead(AlertBase):
    id: UUID
    device_id: UUID
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class AlertListRead(AlertRead):
    device_name: str
    device_uid: str
    customer_name: Optional[str] = None
