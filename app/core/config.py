from functools import lru_cache
from typing import List, Optional, Union

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    debug: bool = True
    project_name: str = "FreightOps API v2"
    environment: str = "development"

    backend_cors_origins: Union[str, List[str]] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:3000",
            "http://localhost:4173",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:4173"
        ],
        validation_alias=AliasChoices("backend_cors_origins", "BACKEND_CORS_ORIGINS", "CORS_ORIGINS", "cors_origins")
    )

    @model_validator(mode="before")
    @classmethod
    def parse_cors_origins(cls, values):
        """Parse CORS_ORIGINS from environment variable (comma-separated string or list)."""
        cors_key = None
        for key in ["backend_cors_origins", "BACKEND_CORS_ORIGINS", "CORS_ORIGINS", "cors_origins"]:
            if key in values:
                cors_key = key
                break

        if cors_key and isinstance(values[cors_key], str):
            cors_value = values[cors_key].strip()
            # Handle empty string - remove key to use default
            if not cors_value:
                del values[cors_key]
            else:
                # Split by comma and strip whitespace
                values[cors_key] = [origin.strip() for origin in cors_value.split(",") if origin.strip()]

        return values

    database_url: str  # Required - no default, must be set in .env

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    automation_interval_minutes: int = 30

    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    sms_twilio_account_sid: Optional[str] = None
    sms_twilio_auth_token: Optional[str] = None
    sms_twilio_from_number: Optional[str] = None
    slack_webhook_url: Optional[str] = None

    # AI OCR Configuration
    enable_ai_ocr: bool = True
    ai_ocr_provider: str = "gemini"  # gemini, claude, or openai
    google_ai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Cloudflare R2 Storage Configuration
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket_name: Optional[str] = None
    r2_endpoint_url: Optional[str] = None  # e.g., "https://<account-id>.r2.cloudflarestorage.com"
    r2_public_url: Optional[str] = None  # Public CDN URL if using custom domain, e.g., "https://files.yourdomain.com"

    # Port Integration Configuration
    port_tracking_cache_ttl_seconds: int = 300  # 5 minutes cache for container tracking
    port_api_rate_limit_per_minute: int = 60  # Default rate limit per port API
    port_tracking_cleanup_interval_hours: int = 24  # How often to run cleanup job

    # Port Houston (Navis) API Credentials - FreightOps internal use only
    # Note: These are NOT used for tenant integrations. Each tenant must purchase
    # their own API access from Port Houston. These credentials are for FreightOps
    # internal operations and testing.
    port_houston_client_id: Optional[str] = "pha-freightops"  # FreightOps internal client ID
    port_houston_client_secret: Optional[str] = None  # Set in .env for production

    # APM Terminals API Credentials - FreightOps internal use only
    # APM Terminals (Maersk subsidiary) operates: Mobile (AL), Elizabeth (NJ), Los Angeles (Pier 400)
    # Tenants must provide their own credentials for appointment/ePass features.
    apm_client_id: Optional[str] = None  # Set in .env for production
    apm_client_secret: Optional[str] = None  # Set in .env for production

    # WEX EnCompass API Configuration - Fuel card virtual payments
    # Each tenant must configure their own WEX credentials via integration settings.
    # These are FreightOps-level defaults for testing/demo purposes only.
    wex_org_group_login_id: Optional[str] = None  # WEX Organization Group Login ID
    wex_username: Optional[str] = None  # WEX API username
    wex_password: Optional[str] = None  # WEX API password (set in .env)
    wex_client_id: Optional[str] = None  # OAuth client ID (optional)
    wex_client_secret: Optional[str] = None  # OAuth client secret (optional)
    wex_use_oauth: bool = False  # Use OAuth2 instead of Basic Auth
    wex_api_base_url: str = "https://wexpayservices.encompass-suite.com/api"
    wex_okta_token_url: str = "https://cp-wex.okta.com/oauth2/ausc718h9qVT8xzSS357/v1/token"

    # Base URL for OAuth callbacks and webhooks
    base_url: str = "https://www.freightopspro.com"  # Production URL
    api_base_url: Optional[str] = None  # API base URL (defaults to base_url/api if not set)

    def get_api_base_url(self) -> str:
        """Get the API base URL, defaulting to base_url/api if not explicitly set."""
        if self.api_base_url:
            return self.api_base_url
        return f"{self.base_url}/api"

    # Stripe Configuration for Billing
    # Test mode keys (for development/staging)
    stripe_test_secret_key: Optional[str] = None
    stripe_test_publishable_key: Optional[str] = None
    stripe_test_webhook_secret: Optional[str] = None
    stripe_test_product_id: Optional[str] = None
    stripe_test_addon_products: dict = Field(
        default={
            "port_integration": None,
            "check_payroll": None,
        }
    )

    # Live mode keys (for production)
    stripe_live_secret_key: Optional[str] = None
    stripe_live_publishable_key: Optional[str] = None
    stripe_live_webhook_secret: Optional[str] = None
    stripe_live_product_id: Optional[str] = None
    stripe_live_addon_products: dict = Field(
        default={
            "port_integration": None,
            "check_payroll": None,
        }
    )

    # Switch between test and live mode
    # Set to True for production, False for development/staging
    stripe_use_live_mode: bool = False

    def get_stripe_secret_key(self) -> Optional[str]:
        """Get the appropriate Stripe secret key based on mode"""
        return self.stripe_live_secret_key if self.stripe_use_live_mode else self.stripe_test_secret_key

    def get_stripe_publishable_key(self) -> Optional[str]:
        """Get the appropriate Stripe publishable key based on mode"""
        return self.stripe_live_publishable_key if self.stripe_use_live_mode else self.stripe_test_publishable_key

    def get_stripe_webhook_secret(self) -> Optional[str]:
        """Get the appropriate Stripe webhook secret based on mode"""
        return self.stripe_live_webhook_secret if self.stripe_use_live_mode else self.stripe_test_webhook_secret

    def get_stripe_product_id(self) -> Optional[str]:
        """Get the appropriate Stripe product ID based on mode"""
        return self.stripe_live_product_id if self.stripe_use_live_mode else self.stripe_test_product_id

    def get_stripe_addon_products(self) -> dict:
        """Get the appropriate Stripe addon product IDs based on mode"""
        return self.stripe_live_addon_products if self.stripe_use_live_mode else self.stripe_test_addon_products


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

