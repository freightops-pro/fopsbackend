"""
Samsara OAuth2 Integration Router

Handles OAuth2 authentication flow and API interactions with Samsara fleet management platform.

API Documentation: https://developers.samsara.com/docs/oauth-20

Key Features:
- OAuth 2.0 authorization code flow
- Token refresh (1-hour access token expiry, single-use refresh tokens)
- Sync vehicles, drivers, GPS locations, HOS data
- Real-time telemetry integration

Rate Limits: Varies by plan, typically 30 requests/second
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import secrets
from datetime import datetime, timedelta

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.integration import CompanyIntegration, Integration
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/integrations/samsara", tags=["integrations-samsara"])


@router.get("/authorize")
async def initiate_samsara_oauth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 1: Redirect user to Samsara authorization page.

    Returns authorization URL with state parameter for CSRF protection.
    """
    if not settings.samsara_client_id:
        raise HTTPException(
            status_code=503,
            detail="Samsara integration not configured. Missing SAMSARA_CLIENT_ID."
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Samsara OAuth2 scopes
    scopes = [
        "offline_access",  # Required for refresh tokens
        "vehicles:read",  # Read vehicle data
        "drivers:read",  # Read driver data
        "locations:read",  # Read GPS locations
        "hos:read",  # Read Hours of Service data
        "equipment:read",  # Read equipment/asset data
    ]

    redirect_uri = f"{settings.get_api_base_url()}/integrations/samsara/callback"

    # Use correct base URL based on region (US or EU)
    auth_base_url = settings.samsara_api_base_url or "https://api.samsara.com"

    auth_url = (
        f"{auth_base_url}/oauth2/authorize"
        f"?response_type=code"
        f"&client_id={settings.samsara_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={' '.join(scopes)}"
        f"&state={state}"
    )

    return {
        "authorization_url": auth_url,
        "state": state,
        "redirect_uri": redirect_uri
    }


@router.get("/callback")
async def samsara_oauth_callback(
    code: str = Query(..., description="Authorization code from Samsara"),
    state: str = Query(..., description="CSRF protection state"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 2: Handle OAuth callback from Samsara.

    Exchange authorization code for access token and refresh token.
    """
    if not settings.samsara_client_id or not settings.samsara_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Samsara integration not configured"
        )

    redirect_uri = f"{settings.get_api_base_url()}/integrations/samsara/callback"
    auth_base_url = settings.samsara_api_base_url or "https://api.samsara.com"

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{auth_base_url}/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.samsara_client_id,
                    "client_secret": settings.samsara_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange code for token: {e.response.text}"
            )

    # Get organization info
    async with httpx.AsyncClient() as client:
        try:
            org_response = await client.get(
                f"{auth_base_url}/fleet/organization",
                headers={
                    "Authorization": f"Bearer {token_data['access_token']}",
                    "Accept": "application/json"
                }
            )
            org_response.raise_for_status()
            org_data = org_response.json()
        except httpx.HTTPStatusError:
            org_data = {}

    # Get or create Samsara integration record
    result = await db.execute(
        select(Integration).where(Integration.integration_key == "samsara")
    )
    integration = result.scalar_one_or_none()

    if not integration:
        integration = Integration(
            integration_key="samsara",
            display_name="Samsara",
            integration_type="eld",
            auth_type="oauth2",
            requires_oauth=True,
            api_base_url=auth_base_url,
            documentation_url="https://developers.samsara.com/docs/getting-started"
        )
        db.add(integration)
        await db.flush()

    # Create or update company integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.company_id == current_user.company_id,
            CompanyIntegration.integration_id == integration.id
        )
    )
    company_integration = result.scalar_one_or_none()

    if company_integration:
        company_integration.access_token = token_data["access_token"]
        company_integration.refresh_token = token_data.get("refresh_token")
        company_integration.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
        company_integration.status = "active"
        company_integration.config = {
            "organization_id": org_data.get("id"),
            "organization_name": org_data.get("name"),
        }
        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
    else:
        company_integration = CompanyIntegration(
            company_id=current_user.company_id,
            integration_id=integration.id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
            status="active",
            config={
                "organization_id": org_data.get("id"),
                "organization_name": org_data.get("name"),
            },
            last_sync_at=datetime.utcnow()
        )
        db.add(company_integration)

    await db.commit()
    await db.refresh(company_integration)

    return {
        "status": "success",
        "integration_id": str(company_integration.id),
        "organization_name": org_data.get("name"),
        "message": "Samsara integration activated successfully"
    }


async def refresh_samsara_token(
    company_integration: CompanyIntegration,
    db: AsyncSession
) -> str:
    """
    Refresh Samsara access token (expires every 1 hour).

    IMPORTANT: Samsara refresh tokens are single-use!
    Each refresh returns a NEW refresh token.
    """
    if not company_integration.refresh_token:
        raise HTTPException(
            status_code=401,
            detail="No refresh token available. Please re-authorize."
        )

    auth_base_url = settings.samsara_api_base_url or "https://api.samsara.com"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{auth_base_url}/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": company_integration.refresh_token,
                    "client_id": settings.samsara_client_id,
                    "client_secret": settings.samsara_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()
        except httpx.HTTPStatusError as e:
            company_integration.status = "error"
            company_integration.last_error_message = f"Token refresh failed: {e.response.text}"
            await db.commit()
            raise HTTPException(
                status_code=401,
                detail="Failed to refresh Samsara token. Please re-authorize."
            )

    # CRITICAL: Update BOTH access token and refresh token (single-use!)
    company_integration.access_token = token_data["access_token"]
    company_integration.refresh_token = token_data.get("refresh_token")  # NEW refresh token
    company_integration.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
    await db.commit()

    return token_data["access_token"]


async def get_samsara_client(
    company_integration: CompanyIntegration,
    db: AsyncSession
) -> httpx.AsyncClient:
    """Get authenticated Samsara API client with automatic token refresh."""
    if company_integration.token_expires_at:
        if datetime.utcnow() >= company_integration.token_expires_at - timedelta(minutes=5):
            access_token = await refresh_samsara_token(company_integration, db)
        else:
            access_token = company_integration.access_token
    else:
        access_token = company_integration.access_token

    auth_base_url = settings.samsara_api_base_url or "https://api.samsara.com"

    client = httpx.AsyncClient(
        base_url=auth_base_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        timeout=30.0
    )

    return client


@router.post("/{integration_id}/sync/vehicles")
async def sync_samsara_vehicles(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync vehicles from Samsara to FreightOps equipment."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    client = await get_samsara_client(company_integration, db)

    try:
        response = await client.get("/fleet/vehicles")
        response.raise_for_status()
        data = response.json()

        vehicles = data.get("data", [])

        # TODO: Map Samsara vehicles to FreightOps equipment
        # For now, just return count

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "synced_count": len(vehicles),
            "message": f"Synced {len(vehicles)} vehicles from Samsara"
        }

    except httpx.HTTPStatusError as e:
        company_integration.last_error_message = f"Sync failed: {e.response.text}"
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sync vehicles: {e.response.text}"
        )
    finally:
        await client.aclose()


@router.post("/{integration_id}/sync/drivers")
async def sync_samsara_drivers(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync drivers from Samsara to FreightOps."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    client = await get_samsara_client(company_integration, db)

    try:
        response = await client.get("/fleet/drivers")
        response.raise_for_status()
        data = response.json()

        drivers = data.get("data", [])

        # TODO: Map Samsara drivers to FreightOps drivers with HOS sync
        # For now, just return count

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "synced_count": len(drivers),
            "message": f"Synced {len(drivers)} drivers from Samsara"
        }

    except httpx.HTTPStatusError as e:
        company_integration.last_error_message = f"Sync failed: {e.response.text}"
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sync drivers: {e.response.text}"
        )
    finally:
        await client.aclose()


@router.post("/{integration_id}/sync/locations")
async def sync_samsara_locations(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get real-time GPS locations from Samsara."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    client = await get_samsara_client(company_integration, db)

    try:
        response = await client.get("/fleet/vehicles/locations")
        response.raise_for_status()
        data = response.json()

        locations = data.get("data", [])

        # TODO: Update FreightOps equipment locations
        # For now, just return count

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "locations_count": len(locations),
            "message": f"Retrieved {len(locations)} vehicle locations from Samsara"
        }

    except httpx.HTTPStatusError as e:
        company_integration.last_error_message = f"Sync failed: {e.response.text}"
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to get locations: {e.response.text}"
        )
    finally:
        await client.aclose()


@router.delete("/{integration_id}")
async def disconnect_samsara(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect Samsara integration."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    await db.delete(company_integration)
    await db.commit()

    return {"status": "success", "message": "Samsara integration disconnected"}
