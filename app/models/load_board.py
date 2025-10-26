from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, JSON, Index
from sqlalchemy.orm import relationship
from app.config.db import Base
from datetime import datetime
import uuid

class LoadBoard(Base):
    __tablename__ = "load_board"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    broker_company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    load_id = Column(String, ForeignKey("simple_loads.id"), nullable=False)
    posted_rate = Column(Numeric(10, 2), nullable=False)
    commission_percentage = Column(Numeric(5, 2), nullable=False)
    is_available = Column(Boolean, default=True)
    booking_requests = Column(JSON, nullable=True)  # Store booking request data
    carrier_company_id = Column(String, ForeignKey("companies.id"), nullable=True)  # Assigned carrier
    booking_confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    broker_company = relationship("Companies", foreign_keys=[broker_company_id])
    carrier_company = relationship("Companies", foreign_keys=[carrier_company_id])
    load = relationship("SimpleLoad", back_populates="load_board_entry")
    
    # Indexes
    __table_args__ = (
        Index('idx_load_board_broker', 'broker_company_id', 'is_available'),
        Index('idx_load_board_carrier', 'carrier_company_id'),
        Index('idx_load_board_load', 'load_id'),
        Index('idx_load_board_available', 'is_available', 'created_at'),
    )

class LoadBooking(Base):
    __tablename__ = "load_bookings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    load_board_id = Column(String, ForeignKey("load_board.id"), nullable=False)
    carrier_company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    requested_rate = Column(Numeric(10, 2), nullable=False)
    message = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending, accepted, rejected, cancelled
    broker_response = Column(String, nullable=True)
    broker_rate = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    load_board = relationship("LoadBoard")
    carrier_company = relationship("Companies")
    
    # Indexes
    __table_args__ = (
        Index('idx_load_bookings_board', 'load_board_id', 'status'),
        Index('idx_load_bookings_carrier', 'carrier_company_id', 'status'),
        Index('idx_load_bookings_status', 'status', 'created_at'),
    )
