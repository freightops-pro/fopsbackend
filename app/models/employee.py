from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, func
from app.config.db import Base


class Employee(Base):
    """Generic employee record (drivers and office staff).

    Driver operational data stays in Driver table; this powers HR directory.
    """

    __tablename__ = "employees"

    id = Column(String, primary_key=True, index=True)
    companyId = Column(String, ForeignKey("companies.id"), nullable=True, index=True)
    name = Column(String, nullable=False, index=True)
    position = Column(String, nullable=True, index=True)
    department = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, server_default="Active", index=True)
    hireDate = Column(DateTime, nullable=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone = Column(String, nullable=True)
    cdlClass = Column(String, nullable=True)
    experienceYears = Column(Integer, nullable=True, server_default="0")
    location = Column(String, nullable=True)
    profileInitials = Column(String, nullable=True)
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
