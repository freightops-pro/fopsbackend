"""HQ System Module model for maintenance mode toggles."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class ModuleStatus(str, enum.Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    DISABLED = "disabled"


class HQSystemModule(Base):
    """System module status for maintenance toggles."""

    __tablename__ = "hq_system_module"

    id = Column(String, primary_key=True)
    key = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(ModuleStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=ModuleStatus.ACTIVE
    )

    # Maintenance info
    maintenance_message = Column(Text, nullable=True)
    maintenance_end_time = Column(DateTime, nullable=True)

    # Tracking
    last_updated_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    last_updated_at = Column(DateTime, nullable=True, server_default=func.now(), onupdate=func.now())

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    last_updated_by = relationship("HQEmployee", foreign_keys=[last_updated_by_id])
