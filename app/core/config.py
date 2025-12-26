from functools import lru_cache
import os
from typing import List, Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    debug: bool = True
    project_name: str = "FreightOps API v2"
    environment: str = "development"

    # Raw CORS origins string - read from env
    cors_origins_raw: Optional[str] = Field(
        default=None,
        alias="CORS_ORIGINS"
    )

    @computed_field
    @property
    def backend_cors_origins(self) -> List[str]:
        """Parse CORS_ORIGINS from environment variable (comma-separated string)."""
        # Check multiple possible env var names
        raw = self.cors_origins_raw
        if not raw:
            raw = os.environ.get("CORS_ORIGINS") or os.environ.get("BACKEND_CORS_ORIGINS") or ""

        if not raw or not raw.strip():
            return []

        origins = []
        for origin in raw.split(","):
            origin = origin.strip()
            if origin:
                # Normalize protocol to lowercase (Https -> https, Http -> http)
                if origin.lower().startswith("https://"):
                    origin = "https://" + origin[8:]
                elif origin.lower().startswith("http://"):
                    origin = "http://" + origin[7:]
                # Upgrade http to https for Railway domains (they always use https)
                if ".up.railway.app" in origin and origin.startswith("http://"):
                    origin = "https://" + origin[7:]
                origins.append(origin)
        return origins

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
    groq_api_key: Optional[str] = None

    # FMCSA Motor Carrier Census API
    fmcsa_app_token: Optional[str] = None
    fmcsa_secret_token: Optional[str] = None

    # Cloudflare R2 Storage Configuration
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket_name: Optional[str] = None
    r2_endpoint_url: Optional[str] = None  # e.g., "https://<account-id>.r2.cloudflarestorage.com"
    r2_public_url: Optional[str] = None  # Public CDN URL if using custom domain, e.g., "https://files.yourdomain.com"

    # Synctera Banking API Configuration
    # Sign up at: https://synctera.com/sandbox
    # Docs: https://dev.synctera.com/
    synctera_api_key: Optional[str] = None
    synctera_api_url: str = "https://api.synctera.com"
    synctera_environment: str = "sandbox"  # sandbox or production
    synctera_webhook_secret: Optional[str] = None

    # HQ Company Configuration
    # HQ (FreightOps HQ) is treated as a company in the system for banking, accounting, etc.
    hq_company_id: Optional[str] = None  # UUID of the HQ company record

    # Plaid External Bank Integration
    # Sign up at: https://dashboard.plaid.com/signup
    # Docs: https://plaid.com/docs/
    plaid_client_id: Optional[str] = None
    plaid_secret: Optional[str] = None
    plaid_environment: str = "sandbox"  # sandbox, development, or production
    plaid_encryption_key: Optional[str] = None  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

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

    # Xero Integration (Accounting)
    xero_client_id: Optional[str] = None
    xero_client_secret: Optional[str] = None

    # Gusto Integration (Payroll & HR)
    gusto_client_id: Optional[str] = None
    gusto_client_secret: Optional[str] = None

    # Check Payroll Integration
    # Sign up at: https://checkhq.com
    # Docs: https://docs.checkhq.com
    check_api_key: Optional[str] = None  # Bearer token for API authentication
    check_environment: str = "sandbox"  # sandbox or production
    check_api_base_url: str = "https://sandbox.checkhq.com"  # Use https://api.checkhq.com for production
    check_hq_company_id: Optional[str] = None  # HQ's own Check company ID for internal payroll

    # Samsara Integration (Fleet Management & ELD)
    samsara_client_id: Optional[str] = None
    samsara_client_secret: Optional[str] = None
    samsara_api_base_url: str = "https://api.samsara.com"  # Or https://api.eu.samsara.com for EU

    # AtoB Fuel Card Integration (OAuth2)
    # Modern API-first fuel card platform
    # Get credentials at: https://www.atob.com/dev-home
    atob_client_id: Optional[str] = None
    atob_client_secret: Optional[str] = None

    # ===== PORT INTEGRATIONS =====
    # Container tracking via PORT terminal APIs (not steamship lines)
    # One port API = all carriers at that port (more efficient)

    # GPA Savannah - Navis N4 EVP API (OAuth2)
    # Contact GPA Customer Service at 912-963-5526 or [email protected] for API access
    # EDI inquiries: [email protected]
    gpa_savannah_client_id: Optional[str] = None
    gpa_savannah_client_secret: Optional[str] = None

    # LBCT (Long Beach Container Terminal) API
    # First terminal at LA/LB to offer public API
    # Register at: https://portal.lbct.com/
    # Docs: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/lbct.html
    lbct_api_key: Optional[str] = None

    # eModal API (used by multiple LA/LB terminals)
    # Terminals: TraPac, YTI, Everport, SSA, TTI, PCT
    # Docs: http://coredocs.envaseconnect.cloud/track-trace/providers/pr/emodal.html
    emodal_api_key: Optional[str] = None
    emodal_sas_token: Optional[str] = None  # SharedAccessSignature for Service Bus
    emodal_topic: str = "envase"  # Service Bus topic

    # BNSF Railway Intermodal API (OAuth2)
    # For tracking containers on rail
    # Docs: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/bnsf.html
    bnsf_client_id: Optional[str] = None
    bnsf_client_secret: Optional[str] = None

    # Union Pacific Rail API (if available)
    up_client_id: Optional[str] = None
    up_client_secret: Optional[str] = None

    # NY/NJ Terminal APIs
    # PNCT (Ports America MTOS): https://mtosportalec.portsamerica.com/
    # APM Elizabeth: Uses apm_client_id/apm_client_secret above
    # GCT: https://www.gcterminals.com/

    # ITS (International Transportation Service) - Long Beach
    # Docs: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/its.html
    its_username: Optional[str] = None
    its_password: Optional[str] = None

    # ICTSI (International Container Terminal Services Inc.)
    # Global terminal operator - uses Azure API Management
    # Docs: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/ictsi.html
    ictsi_subscription_id: Optional[str] = None
    ictsi_subscription_key: Optional[str] = None

    # Florida Ports
    # Port Everglades: Uses Tideworks scraper (pet.tideworks.io)
    # Port Miami: APM Terminals (uses apm_client_id above)
    # JAXPORT: SSA Marine / Various

    # Terminal49 API (third-party aggregator - fallback option)
    # Sign up at: https://terminal49.com
    # Docs: https://terminal49.com/docs/home
    terminal49_api_key: Optional[str] = None

    # Stripe Configuration for Billing
    # Test mode keys (for development/staging)
    stripe_test_secret_key: Optional[str] = None
    stripe_test_publishable_key: Optional[str] = None
    stripe_test_webhook_secret: Optional[str] = None
    stripe_test_product_id: Optional[str] = None
    stripe_test_addon_products: Optional[dict] = Field(
        default_factory=lambda: {
            "port_integration": None,
            "check_payroll": None,
        }
    )

    # Live mode keys (for production)
    stripe_live_secret_key: Optional[str] = None
    stripe_live_publishable_key: Optional[str] = None
    stripe_live_webhook_secret: Optional[str] = None
    stripe_live_product_id: Optional[str] = None
    stripe_live_addon_products: Optional[dict] = Field(
        default_factory=lambda: {
            "port_integration": None,
            "check_payroll": None,
        }
    )

    # Switch between test and live mode
    # Set to True for production, False for development/staging
    stripe_use_live_mode: bool = False

    # Legacy/simple Stripe keys (fallback if test/live specific keys not set)
    stripe_secret_key: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_product_id: Optional[str] = None
    stripe_addon_products: Optional[dict] = None

    def _is_valid_stripe_key(self, key: Optional[str]) -> bool:
        """Check if a Stripe key is valid (not None and not a placeholder)"""
        if not key:
            return False
        # Check for common placeholder patterns
        placeholders = ["CHANGE_ME", "change_me", "YOUR_", "your_", "PLACEHOLDER", "placeholder"]
        return not any(p in key for p in placeholders)

    def get_stripe_secret_key(self) -> Optional[str]:
        """Get the appropriate Stripe secret key based on mode, with fallback to simple key"""
        if self.stripe_use_live_mode:
            if self._is_valid_stripe_key(self.stripe_live_secret_key):
                return self.stripe_live_secret_key
            return self.stripe_secret_key
        if self._is_valid_stripe_key(self.stripe_test_secret_key):
            return self.stripe_test_secret_key
        return self.stripe_secret_key

    def get_stripe_publishable_key(self) -> Optional[str]:
        """Get the appropriate Stripe publishable key based on mode, with fallback to simple key"""
        if self.stripe_use_live_mode:
            if self._is_valid_stripe_key(self.stripe_live_publishable_key):
                return self.stripe_live_publishable_key
            return self.stripe_publishable_key
        if self._is_valid_stripe_key(self.stripe_test_publishable_key):
            return self.stripe_test_publishable_key
        return self.stripe_publishable_key

    def get_stripe_webhook_secret(self) -> Optional[str]:
        """Get the appropriate Stripe webhook secret based on mode, with fallback to simple key"""
        if self.stripe_use_live_mode:
            if self._is_valid_stripe_key(self.stripe_live_webhook_secret):
                return self.stripe_live_webhook_secret
            return self.stripe_webhook_secret
        if self._is_valid_stripe_key(self.stripe_test_webhook_secret):
            return self.stripe_test_webhook_secret
        return self.stripe_webhook_secret

    def get_stripe_product_id(self) -> Optional[str]:
        """Get the appropriate Stripe product ID based on mode, with fallback to simple key"""
        if self.stripe_use_live_mode:
            if self._is_valid_stripe_key(self.stripe_live_product_id):
                return self.stripe_live_product_id
            return self.stripe_product_id
        if self._is_valid_stripe_key(self.stripe_test_product_id):
            return self.stripe_test_product_id
        return self.stripe_product_id

    def get_stripe_addon_products(self) -> dict:
        """Get the appropriate Stripe addon product IDs based on mode, with fallback to simple key"""
        if self.stripe_use_live_mode:
            products = self.stripe_live_addon_products or self.stripe_addon_products
        else:
            products = self.stripe_test_addon_products or self.stripe_addon_products
        return products or {"port_integration": None, "check_payroll": None}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

