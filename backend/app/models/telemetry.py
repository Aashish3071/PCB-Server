import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Float, ForeignKey, DateTime, UUID, Boolean, Integer, UniqueConstraint, Index, String
from typing import TYPE_CHECKING
from .base import Base

if TYPE_CHECKING:
    from .device import Device

class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Telemetry data
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    panel_voltage: Mapped[float | None] = mapped_column(Float, nullable=True)
    charging_current: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_voltage: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    charging_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    light_load_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    signal_strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Metadata / Diagnostics
    hardware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    boot_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    network_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    device: Mapped["Device"] = relationship("Device", back_populates="telemetry")

    __table_args__ = (
        UniqueConstraint("device_id", "timestamp", name="uq_device_timestamp"),
        Index("ix_telemetry_device_id_timestamp_desc", "device_id", "timestamp", postgresql_using='btree'),
    )
