import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import field_validator

class Settings(BaseSettings):
    # CORS Configuration
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,https://fopssid.vercel.app,http://localhost:8081"
    
    @field_validator('ALLOWED_ORIGINS')
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    # Database Configuration - Neon PostgreSQL for production
    DATABASE_URL: str = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@ep-quiet-moon-adsx2dey-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    
    # Neon-specific database optimizations
    DB_POOL_SIZE: int = 20  # Neon handles pooling well
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_SSL_MODE: str = "require"  # Enable SSL for Neon
    
    # JWT Configuration
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Google Cloud Vision OCR Configuration
    GOOGLE_CLOUD_PROJECT_ID: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None  # Alternative to Google Cloud Vision
    OCR_ENABLED: bool = True
    
    # Email Configuration
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: str = "noreply@freightopspro.com"
    FROM_NAME: str = "FreightOps Pro"
    FRONTEND_URL: str = "http://localhost:5173"
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v, info):
        if info.data.get('ENVIRONMENT') == "production":
            if v == "your-super-secret-key-change-this-in-production":
                raise ValueError("Must change SECRET_KEY in production")
            if len(v) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production")
        return v
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "FreightOps Platform"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # External Services
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    RAILSR_API_KEY: str | None = None
    GUSTO_CLIENT_ID: str | None = None
    GUSTO_CLIENT_SECRET: str | None = None
    
    # Synctera Configuration
    SYNCTERA_BASE_URL: str = "https://api.synctera.com/v0"
    SYNCTERA_API_KEY: str | None = None
    SYNCTERA_WEBHOOK_SECRET: str | None = None
    
    # Redis Configuration (Railway Redis)
    REDIS_URL: str | None = None
    
    # Monitoring & Alerting
    SLACK_WEBHOOK_URL: str | None = None
    DISCORD_WEBHOOK_URL: str | None = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()