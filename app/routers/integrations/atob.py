"""
AtoB Fuel Card Integration Router.

AtoB is a modern API-first fuel card platform providing:
- Real-time transaction controls and fraud prevention
- Telematics integration for GPS verification
- Fuel level monitoring to prevent theft
- Competitive fuel discounts
- Mobile app for drivers

API Documentation: https://www.atob.com/dev-home
Website: https://www.atob.com/
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.api import deps
from app.core.db import get_db
from app.core.config import settings
from app.models.integration import CompanyIntegration, Integration
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/atob", tags=["Integrations - AtoB"])


# AtoB API Configuration
ATOB_AUTH_URL = "https://api.atob.com/oauth/authorize"
ATOB_TOKEN_URL = "https://api.atob.com/oauth/token"
ATOB_API_BASE = "https://api.atob.com/v1"


# ==================== SCHEMAS ====================


class AtoBCard(BaseModel):
    """AtoB fuel card details."""
    id: str
    card_number_last4: str
    status: str  # active, blocked, expired
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    vehicle_id: Optional[str] = None
    vehicle_vin: Optional[str] = None
    spending_limit: Optional[float] = None
    daily_limit: Optional[float] = None
    gps_lock_enabled: bool = False
    fuel_level_check_enabled: bool = False
    created_at: datetime
    last_used_at: Optional[datetime] = None


class AtoBTransaction(BaseModel):
    """AtoB transaction record."""
    id: str
    card_id: str
    transaction_date: datetime
    merchant_name: str
    merchant_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    fuel_type: Optional[str] = None
    gallons: Optional[float] = None
    price_per_gallon: Optional[float] = None
    subtotal: float
    discount_amount: float = 0
    total_amount: float
    odometer: Optional[int] = None
    vehicle_fuel_level_before: Optional[float] = None
    vehicle_fuel_level_after: Optional[float] = None
    gps_verified: bool = False
    suspicious_activity: bool = False
    driver_id: Optional[str] = None


class AtoBAlert(BaseModel):
    """AtoB fraud/suspicious activity alert."""
    id: str
    alert_type: str  # gps_mismatch, fuel_level_anomaly, unusual_amount, etc.
    severity: str  # low, medium, high, critical
    card_id: str
    transaction_id: Optional[str] = None
    description: str
    created_at: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class CreateCardRequest(BaseModel):
    """Request to create a new AtoB card."""
    driver_id: Optional[str] = Field(None, description="Driver ID to assign")
    vehicle_id: Optional[str] = Field(None, description="Vehicle ID to assign")
    spending_limit: Optional[float] = Field(None, ge=0, description="Per-transaction limit")
    daily_limit: Optional[float] = Field(None, ge=0, description="Daily spending limit")
    enable_gps_lock: bool = Field(default=True, description="Require GPS verification")
    enable_fuel_level_check: bool = Field(default=False, description="Check fuel level")


class UpdateCardRequest(BaseModel):
    """Request to update card settings."""
    spending_limit: Optional[float] = Field(None, ge=0)
    daily_limit: Optional[float] = Field(None, ge=0)
    enable_gps_lock: Optional[bool] = None
    enable_fuel_level_check: Optional[bool] = None
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None


class TelematicsConfig(BaseModel):
    """Telematics provider configuration."""
    provider: str  # samsara, motive, geotab, etc.
    api_key: Optional[str] = None
    webhook_url: Optional[str] = None


# ==================== OAUTH2 AUTHENTICATION ====================


async def get_current_user(current_user: User = Depends(deps.get_current_user)) -> User:
    return current_user


async def get_atob_integration(
    db: AsyncSession,
    company_id: str,
) -> CompanyIntegration:
    """Get active AtoB integration for company."""
    result = await db.execute(
        select(CompanyIntegration)
        .join(Integration)
        .where(
            CompanyIntegration.company_id == company_id,
            Integration.integration_key == "atob",
            CompanyIntegration.status == "active",
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AtoB integration not configured. Please activate AtoB in integration settings."
        )

    return integration


async def get_valid_access_token(
    integration: CompanyIntegration,
    db: AsyncSession,
) -> str:
    """Get valid access token, refreshing if necessary."""
    # Check if token needs refresh (5 min buffer)
    if integration.token_expires_at and integration.token_expires_at <= datetime.utcnow() + timedelta(minutes=5):
        await refresh_atob_token(integration, db)

    return integration.access_token


async def refresh_atob_token(
    integration: CompanyIntegration,
    db: AsyncSession,
) -> None:
    """Refresh AtoB OAuth access token."""
    if not integration.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AtoB refresh token not available. Please reconnect."
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ATOB_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": integration.refresh_token,
                    "client_id": settings.atob_client_id,
                    "client_secret": settings.atob_client_secret,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(f"AtoB token refresh failed: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to refresh AtoB token. Please reconnect."
                )

            token_data = response.json()

            integration.access_token = token_data["access_token"]
            integration.refresh_token = token_data.get("refresh_token", integration.refresh_token)
            integration.token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_data.get("expires_in", 3600)
            )
            integration.updated_at = datetime.utcnow()

            await db.commit()

    except httpx.RequestError as e:
        logger.error(f"AtoB token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


# ==================== OAUTH2 FLOW ====================


@router.get("/authorize")
async def initiate_oauth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 1: Initiate AtoB OAuth2 authorization flow.

    Returns the authorization URL to redirect the user to AtoB's login page.
    """
    if not settings.atob_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AtoB integration not configured. Missing client credentials."
        )

    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state in session or cache (simplified for example)
    # In production, use Redis or similar

    redirect_uri = f"{settings.get_api_base_url()}/integrations/atob/callback"

    scopes = [
        "cards:read",
        "cards:write",
        "transactions:read",
        "drivers:read",
        "vehicles:read",
        "alerts:read",
    ]

    params = {
        "client_id": settings.atob_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
    }

    auth_url = f"{ATOB_AUTH_URL}?{urlencode(params)}"

    return {
        "authorization_url": auth_url,
        "state": state,
    }


@router.get("/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State token"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 2: Handle OAuth2 callback from AtoB.

    Exchanges authorization code for access and refresh tokens.
    """
    # Validate state token (should check against stored state)

    redirect_uri = f"{settings.get_api_base_url()}/integrations/atob/callback"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ATOB_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.atob_client_id,
                    "client_secret": settings.atob_client_secret,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(f"AtoB token exchange failed: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange authorization code"
                )

            token_data = response.json()

    except httpx.RequestError as e:
        logger.error(f"AtoB token exchange error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )

    company_id = current_user.company_id

    # Get or create AtoB integration
    result = await db.execute(
        select(Integration).where(Integration.integration_key == "atob")
    )
    integration = result.scalar_one_or_none()

    if not integration:
        integration = Integration(
            id=secrets.token_hex(16),
            integration_key="atob",
            name="AtoB",
            category="fuel_cards",
            description="Modern fuel card with real-time controls and telematics integration",
            auth_type="oauth2",
            is_active=True,
        )
        db.add(integration)
        await db.flush()

    # Check for existing company integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.company_id == company_id,
            CompanyIntegration.integration_id == integration.id,
        )
    )
    company_integration = result.scalar_one_or_none()

    if company_integration:
        company_integration.access_token = token_data["access_token"]
        company_integration.refresh_token = token_data.get("refresh_token")
        company_integration.token_expires_at = datetime.utcnow() + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )
        company_integration.status = "active"
        company_integration.updated_at = datetime.utcnow()
    else:
        company_integration = CompanyIntegration(
            id=secrets.token_hex(16),
            company_id=company_id,
            integration_id=integration.id,
            status="active",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=datetime.utcnow() + timedelta(
                seconds=token_data.get("expires_in", 3600)
            ),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(company_integration)

    await db.commit()

    return {
        "status": "connected",
        "message": "Successfully connected to AtoB",
        "integration_key": "atob",
    }


@router.delete("/disconnect")
async def disconnect(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect AtoB integration."""
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)

    # Revoke token with AtoB
    if integration.access_token:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{ATOB_API_BASE}/oauth/revoke",
                    headers={"Authorization": f"Bearer {integration.access_token}"},
                    timeout=10.0,
                )
        except Exception as e:
            logger.warning(f"Failed to revoke AtoB token: {e}")

    integration.status = "inactive"
    integration.access_token = None
    integration.refresh_token = None
    integration.token_expires_at = None
    integration.updated_at = datetime.utcnow()

    await db.commit()

    return {"status": "disconnected", "message": "AtoB integration disconnected"}


@router.get("/status")
async def get_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get AtoB integration status."""
    company_id = current_user.company_id

    try:
        integration = await get_atob_integration(db, company_id)

        # Check token validity
        token_valid = (
            integration.token_expires_at
            and integration.token_expires_at > datetime.utcnow()
        )

        return {
            "status": integration.status,
            "connected": integration.status == "active" and token_valid,
            "token_expires_at": integration.token_expires_at,
            "last_sync": integration.last_sync_at,
        }
    except HTTPException:
        return {
            "status": "not_configured",
            "connected": False,
            "token_expires_at": None,
            "last_sync": None,
        }


# ==================== CARD MANAGEMENT ====================


@router.get("/cards", response_model=List[AtoBCard])
async def list_cards(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    driver_id: Optional[str] = Query(None, description="Filter by driver"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all AtoB fuel cards.

    Returns cards with their settings, assignments, and security features.
    """
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)
    access_token = await get_valid_access_token(integration, db)

    try:
        async with httpx.AsyncClient() as client:
            params = {}
            if status_filter:
                params["status"] = status_filter
            if driver_id:
                params["driver_id"] = driver_id

            response = await client.get(
                f"{ATOB_API_BASE}/cards",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                cards = response.json().get("data", [])
                return [AtoBCard(**card) for card in cards]
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to retrieve cards from AtoB"
                )

    except httpx.RequestError as e:
        logger.error(f"AtoB API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


@router.post("/cards", response_model=AtoBCard)
async def create_card(
    request: CreateCardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new AtoB fuel card.

    Cards can be assigned to drivers/vehicles with spending limits.
    """
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)
    access_token = await get_valid_access_token(integration, db)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ATOB_API_BASE}/cards",
                json={
                    "driver_id": request.driver_id,
                    "vehicle_id": request.vehicle_id,
                    "spending_limit": request.spending_limit,
                    "daily_limit": request.daily_limit,
                    "gps_lock_enabled": request.enable_gps_lock,
                    "fuel_level_check_enabled": request.enable_fuel_level_check,
                },
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 201:
                card_data = response.json().get("data")
                return AtoBCard(**card_data)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create card"
                )

    except httpx.RequestError as e:
        logger.error(f"AtoB API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


@router.patch("/cards/{card_id}")
async def update_card(
    card_id: str,
    request: UpdateCardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update card settings."""
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)
    access_token = await get_valid_access_token(integration, db)

    update_data = request.model_dump(exclude_none=True)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{ATOB_API_BASE}/cards/{card_id}",
                json=update_data,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                return response.json().get("data")
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update card"
                )

    except httpx.RequestError as e:
        logger.error(f"AtoB API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


@router.post("/cards/{card_id}/block")
async def block_card(
    card_id: str,
    reason: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Block a card immediately."""
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)
    access_token = await get_valid_access_token(integration, db)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ATOB_API_BASE}/cards/{card_id}/block",
                json={"reason": reason},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                return {"status": "blocked", "card_id": card_id}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to block card"
                )

    except httpx.RequestError as e:
        logger.error(f"AtoB API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


@router.post("/cards/{card_id}/unblock")
async def unblock_card(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unblock a previously blocked card."""
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)
    access_token = await get_valid_access_token(integration, db)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ATOB_API_BASE}/cards/{card_id}/unblock",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                return {"status": "active", "card_id": card_id}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to unblock card"
                )

    except httpx.RequestError as e:
        logger.error(f"AtoB API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


# ==================== TRANSACTIONS ====================


@router.get("/transactions", response_model=List[AtoBTransaction])
async def get_transactions(
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    card_id: Optional[str] = Query(None, description="Filter by card"),
    suspicious_only: bool = Query(False, description="Only suspicious transactions"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get AtoB transactions with fraud detection data.

    Returns detailed transaction info including:
    - GPS verification status
    - Fuel level before/after
    - Suspicious activity flags
    """
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)
    access_token = await get_valid_access_token(integration, db)

    try:
        async with httpx.AsyncClient() as client:
            params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
            if card_id:
                params["card_id"] = card_id
            if suspicious_only:
                params["suspicious_activity"] = "true"

            response = await client.get(
                f"{ATOB_API_BASE}/transactions",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=60.0,
            )

            if response.status_code == 200:
                transactions = response.json().get("data", [])

                # Update sync timestamp
                integration.last_sync_at = datetime.utcnow()
                await db.commit()

                return [AtoBTransaction(**tx) for tx in transactions]
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to retrieve transactions"
                )

    except httpx.RequestError as e:
        logger.error(f"AtoB API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


# ==================== ALERTS ====================


@router.get("/alerts", response_model=List[AtoBAlert])
async def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    unresolved_only: bool = Query(True, description="Only unresolved alerts"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get fraud and suspicious activity alerts.

    AtoB provides real-time alerts for:
    - GPS location mismatch (vehicle not at fuel station)
    - Fuel level anomalies (purchased fuel > tank capacity)
    - Unusual purchase amounts
    - Duplicate transactions
    """
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)
    access_token = await get_valid_access_token(integration, db)

    try:
        async with httpx.AsyncClient() as client:
            params = {}
            if severity:
                params["severity"] = severity
            if unresolved_only:
                params["resolved"] = "false"

            response = await client.get(
                f"{ATOB_API_BASE}/alerts",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                alerts = response.json().get("data", [])
                return [AtoBAlert(**alert) for alert in alerts]
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to retrieve alerts"
                )

    except httpx.RequestError as e:
        logger.error(f"AtoB API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_note: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an alert as resolved."""
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)
    access_token = await get_valid_access_token(integration, db)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ATOB_API_BASE}/alerts/{alert_id}/resolve",
                json={"resolution_note": resolution_note},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                return {"status": "resolved", "alert_id": alert_id}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to resolve alert"
                )

    except httpx.RequestError as e:
        logger.error(f"AtoB API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


# ==================== TELEMATICS ====================


@router.post("/telematics/configure")
async def configure_telematics(
    config: TelematicsConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Configure telematics provider integration.

    AtoB integrates with telematics providers to:
    - Verify vehicle GPS location at fuel stations
    - Monitor fuel levels to detect theft
    - Auto-assign drivers to vehicles
    """
    company_id = current_user.company_id
    integration = await get_atob_integration(db, company_id)
    access_token = await get_valid_access_token(integration, db)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ATOB_API_BASE}/telematics/configure",
                json=config.model_dump(exclude_none=True),
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                return {
                    "status": "configured",
                    "provider": config.provider,
                    "message": f"Telematics integration with {config.provider} configured"
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to configure telematics"
                )

    except httpx.RequestError as e:
        logger.error(f"AtoB API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to AtoB"
        )


# ==================== IFTA REPORTING ====================


@router.post("/sync-ifta")
async def sync_ifta(
    quarter: str = Query(..., description="IFTA quarter (e.g., '2025-Q1')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync AtoB transactions for IFTA reporting.

    AtoB provides detailed location data (including lat/long) for accurate
    jurisdiction assignment.
    """
    company_id = current_user.company_id

    # Parse quarter
    year, q = quarter.split("-Q")
    quarter_starts = {"1": (1, 1), "2": (4, 1), "3": (7, 1), "4": (10, 1)}
    quarter_ends = {"1": (3, 31), "2": (6, 30), "3": (9, 30), "4": (12, 31)}

    start_month, start_day = quarter_starts[q]
    end_month, end_day = quarter_ends[q]

    start_date = datetime(int(year), start_month, start_day)
    end_date = datetime(int(year), end_month, end_day, 23, 59, 59)

    # Get transactions
    transactions = await get_transactions(
        start_date=start_date,
        end_date=end_date,
        card_id=None,
        suspicious_only=False,
        db=db,
        current_user=current_user,
    )

    # Aggregate by state
    state_totals = {}
    total_discount = 0

    for tx in transactions:
        state = tx.state or "UNKNOWN"
        if state not in state_totals:
            state_totals[state] = {
                "gallons": 0,
                "amount": 0,
                "discount": 0,
                "transactions": 0,
            }
        state_totals[state]["gallons"] += tx.gallons or 0
        state_totals[state]["amount"] += tx.total_amount
        state_totals[state]["discount"] += tx.discount_amount
        state_totals[state]["transactions"] += 1
        total_discount += tx.discount_amount

    return {
        "quarter": quarter,
        "synced_at": datetime.utcnow().isoformat(),
        "total_transactions": len(transactions),
        "total_gallons": sum(tx.gallons or 0 for tx in transactions),
        "total_amount": sum(tx.total_amount for tx in transactions),
        "total_discount": total_discount,
        "by_jurisdiction": state_totals,
    }


# ==================== WEBHOOKS ====================


@router.post("/webhooks")
async def handle_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle AtoB webhook notifications.

    AtoB sends webhooks for:
    - Real-time transaction notifications
    - Fraud alerts
    - Card status changes
    """
    # Verify webhook signature (should use HMAC in production)
    body = await request.json()

    event_type = body.get("event_type")
    data = body.get("data", {})

    logger.info(f"Received AtoB webhook: {event_type}")

    if event_type == "transaction.created":
        # Process new transaction
        logger.info(f"New transaction: {data.get('id')}")

    elif event_type == "alert.created":
        # Process new alert
        logger.warning(f"New alert: {data.get('alert_type')} - {data.get('description')}")

    elif event_type == "card.status_changed":
        # Card status update
        logger.info(f"Card {data.get('card_id')} status: {data.get('status')}")

    return {"status": "received", "event_type": event_type}
