from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class DocumentProcessingJob(Base):
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    load_id = Column(String, ForeignKey("freight_load.id"), nullable=True, index=True)

    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    raw_text = Column(Text, nullable=True)
    parsed_payload = Column(JSON, nullable=True)
    field_confidence = Column(JSON, nullable=True)
    errors = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")
    load = relationship("Load")

