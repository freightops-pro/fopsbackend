from sqlalchemy import Column, String, DateTime, Integer, func, Text, JSON
from app.config.db import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, nullable=False)
    companyId = Column(String, index=True, nullable=False)
    
    # Document Information
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # Policy Document, Medical Record, Training Record, etc.
    category = Column(String, nullable=False)  # HR Policies, Driver Compliance, Safety, etc.
    description = Column(Text)
    
    # File Information
    fileName = Column(String, nullable=False)
    fileSize = Column(Integer)  # Size in bytes
    fileType = Column(String)  # PDF, DOC, XLS, etc.
    filePath = Column(String)  # Path to stored file
    
    # Assignment
    employeeId = Column(String, index=True)  # Can be null for company-wide documents
    employeeName = Column(String)  # Denormalized for easier querying
    
    # Status and Metadata
    status = Column(String, default="Active")  # Active, Expired, Archived, etc.
    uploadDate = Column(DateTime, server_default=func.now())
    expiryDate = Column(DateTime)  # Optional, for documents that expire
    
    # Additional structured data
    details = Column(JSON)
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now()) 