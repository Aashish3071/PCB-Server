import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, UUID
from typing import List, TYPE_CHECKING
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .device import Device

class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    devices: Mapped[List["Device"]] = relationship("Device", back_populates="customer", cascade="all, delete-orphan")
