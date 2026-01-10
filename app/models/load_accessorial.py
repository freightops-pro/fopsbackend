from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class LoadAccessorial(Base):
    """Accessorial charges associated with a load (detention, lumper, etc.)"""
    __tablename__ = "load_accessorials"

    id = Column(String, primary_key=True)
    load_id = Column(String, ForeignKey("freight_load.id"), nullable=False, index=True)

    charge_type = Column(String, nullable=False)  # DETENTION, LUMPER, LAYOVER, TONU, FUEL_SURCHARGE, etc.
    description = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=True, default=1)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    load = relationship("Load", back_populates="accessorials")
