from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, JSON, Index
from sqlalchemy.orm import relationship
from app.config.db import Base
from datetime import datetime
import uuid

class BrokerCommission(Base):
    __tablename__ = "broker_commissions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    load_id = Column(String, ForeignKey("simple_loads.id"), nullable=False)
    broker_company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    carrier_company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    total_load_value = Column(Numeric(10, 2), nullable=False)
    commission_percentage = Column(Numeric(5, 2), nullable=False)
    commission_amount = Column(Numeric(10, 2), nullable=False)
    payment_status = Column(String, nullable=False, default="pending")  # pending, paid, disputed
    payment_date = Column(DateTime, nullable=True)
    settlement_id = Column(String, nullable=True)  # Will reference settlements table when it exists
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    load = relationship("SimpleLoad")
    broker_company = relationship("Companies", foreign_keys=[broker_company_id])
    carrier_company = relationship("Companies", foreign_keys=[carrier_company_id])
    # settlement = relationship("Settlement")  # Will be enabled when settlements table exists
    
    # Indexes
    __table_args__ = (
        Index('idx_broker_commissions_broker', 'broker_company_id', 'payment_status'),
        Index('idx_broker_commissions_carrier', 'carrier_company_id'),
        Index('idx_broker_commissions_load', 'load_id'),
        Index('idx_broker_commissions_payment', 'payment_status', 'payment_date'),
    )
