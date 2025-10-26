"""
API Key Management Models
"""
from sqlalchemy import Column, String, DateTime, Text, Boolean, Index
from sqlalchemy.sql import func
from app.config.db import Base
import uuid
import secrets
import hashlib

class APIKey(Base):
    """
    API Key model for managing API access
    """
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Key identification
    name = Column(String, nullable=False)  # Human-readable name for the key
    key_hash = Column(String, nullable=False, unique=True, index=True)  # Hashed version of the key
    key_prefix = Column(String, nullable=False)  # First 8 characters for identification
    
    # Ownership
    company_id = Column(String, nullable=False, index=True)
    created_by = Column(String, nullable=False)  # User ID who created the key
    
    # Key metadata
    description = Column(Text, nullable=True)
    permissions = Column(Text, nullable=True)  # JSON string of allowed endpoints/actions
    
    # Status and lifecycle
    is_active = Column(Boolean, default=True, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    last_used_at = Column(DateTime, nullable=True, index=True)
    usage_count = Column(String, default="0")  # Total number of API calls made
    
    # Rate limiting
    rate_limit_per_hour = Column(String, default="1000")
    rate_limit_per_day = Column(String, default="10000")
    
    # Audit fields
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Create indexes for performance
    __table_args__ = (
        Index('idx_api_key_company_active', 'company_id', 'is_active'),
        Index('idx_api_key_prefix', 'key_prefix'),
        Index('idx_api_key_expires', 'expires_at'),
        Index('idx_api_key_last_used', 'last_used_at'),
    )
    
    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        """
        Generate a new API key
        Returns: (full_key, key_hash, key_prefix)
        """
        # Generate a secure random key
        full_key = f"fk_{secrets.token_urlsafe(32)}"
        
        # Create hash for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        
        # Create prefix for identification
        key_prefix = full_key[:8]
        
        return full_key, key_hash, key_prefix
    
    def verify_key(self, provided_key: str) -> bool:
        """Verify if the provided key matches this API key"""
        provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
        return provided_hash == self.key_hash
    
    def is_expired(self) -> bool:
        """Check if the API key has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if the API key is valid (active and not expired)"""
        return self.is_active and not self.is_expired()

class APIKeyUsage(Base):
    """
    API Key usage tracking for monitoring and rate limiting
    """
    __tablename__ = "api_key_usage"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Key reference
    api_key_id = Column(String, nullable=False, index=True)
    company_id = Column(String, nullable=False, index=True)
    
    # Usage details
    endpoint = Column(String, nullable=False, index=True)
    method = Column(String, nullable=False)
    status_code = Column(String, nullable=False)
    response_time_ms = Column(String, nullable=True)
    
    # Request details
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    # Create indexes for performance
    __table_args__ = (
        Index('idx_usage_key_timestamp', 'api_key_id', 'timestamp'),
        Index('idx_usage_company_timestamp', 'company_id', 'timestamp'),
        Index('idx_usage_endpoint_timestamp', 'endpoint', 'timestamp'),
        Index('idx_usage_hourly', 'api_key_id', 'timestamp'),  # For hourly rate limiting
    )

class APIKeyRateLimit(Base):
    """
    API Key rate limiting tracking
    """
    __tablename__ = "api_key_rate_limits"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Key reference
    api_key_id = Column(String, nullable=False, index=True)
    
    # Rate limit windows
    hour_start = Column(DateTime, nullable=False, index=True)  # Start of the hour
    day_start = Column(DateTime, nullable=False, index=True)   # Start of the day
    
    # Usage counts
    hourly_requests = Column(String, default="0")
    daily_requests = Column(String, default="0")
    
    # Limits
    hourly_limit = Column(String, default="1000")
    daily_limit = Column(String, default="10000")
    
    # Status
    hourly_exceeded = Column(Boolean, default=False)
    daily_exceeded = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Create indexes for performance
    __table_args__ = (
        Index('idx_rate_limit_key_hour', 'api_key_id', 'hour_start'),
        Index('idx_rate_limit_key_day', 'api_key_id', 'day_start'),
        Index('idx_rate_limit_exceeded', 'hourly_exceeded', 'daily_exceeded'),
    )

