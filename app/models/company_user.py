from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.config.db import Base
from datetime import datetime
import uuid

class CompanyUser(Base):
    __tablename__ = "company_users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    role = Column(String, nullable=False)  # carrier, broker, dispatcher, admin, accounting, compliance
    permissions = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("Users", back_populates="company_users")
    company = relationship("Companies", back_populates="company_users")
    
    # Multi-tenant indexes
    __table_args__ = (
        Index('idx_company_users_company', 'company_id', 'is_active'),
        Index('idx_company_users_user', 'user_id', 'is_active'),
        Index('idx_company_users_role', 'company_id', 'role'),
    )
