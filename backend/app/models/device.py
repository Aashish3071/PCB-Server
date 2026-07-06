import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, UUID, UniqueConstraint, Integer
from typing import List, TYPE_CHECKING
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .customer import Customer
    from .telemetry import Telemetry
    from .alert import Alert

class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_uid: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    device_name: Mapped[str] = mapped_column(String, nullable=False)
    device_type: Mapped[str] = mapped_column(String, default="solar_rms", nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String, nullable=False)
    firmware_version: Mapped[str | None] = mapped_column(String, nullable=True)
    installation_location: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="OFFLINE", nullable=False) # ONLINE, OFFLINE, DISABLED, MAINTENANCE
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    # Returned to the device as next_upload_seconds on every telemetry response;
    # also drives the offline-watchdog threshold (interval * grace multiplier).
    upload_interval_seconds: Mapped[int] = mapped_column(Integer, default=300, server_default="300", nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="devices")
    telemetry: Mapped[List["Telemetry"]] = relationship("Telemetry", back_populates="device", cascade="all, delete-orphan")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="device", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("customer_id", "device_name", name="uq_customer_device_name"),
    )
