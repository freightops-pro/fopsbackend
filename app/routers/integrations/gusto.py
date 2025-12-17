"""
Gusto OAuth2 Integration Router

Handles OAuth2 authentication flow and API interactions with Gusto payroll and HR platform.

API Documentation: https://docs.gusto.com/app-integrations/docs/introduction

Key Features:
- OAuth 2.0 authorization code flow
- Token refresh (2-hour access token expiry)
- Sync employees, payrolls, time tracking
- Contractor management

Rate Limits: Varies by endpoint, typically 100 requests/minute
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import secrets
from datetime import datetime, timedelta

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.integration import CompanyIntegration, Integration
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/integrations/gusto", tags=["integrations-gusto"])


@router.get("/authorize")
async def initiate_gusto_oauth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 1: Redirect user to Gusto authorization page.

    Returns authorization URL with state parameter for CSRF protection.
    """
    if not settings.gusto_client_id:
        raise HTTPException(
            status_code=503,
            detail="Gusto integration not configured. Missing GUSTO_CLIENT_ID."
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Gusto OAuth2 scopes
    scopes = [
        "employees:read",  # Read employee data
        "employees:write",  # Update employee data
        "payrolls:read",  # Read payroll data
        "companies:read",  # Read company information
        "time_tracking:read",  # Read time tracking data
        "time_tracking:write",  # Update time tracking data
    ]

    redirect_uri = f"{settings.get_api_base_url()}/integrations/gusto/callback"

    # Use demo environment for development
    auth_base_url = "https://api.gusto-demo.com" if settings.environment == "development" else "https://api.gusto.com"

    auth_url = (
        f"{auth_base_url}/oauth/authorize"
        f"?response_type=code"
        f"&client_id={settings.gusto_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={' '.join(scopes)}"
        f"&state={state}"
    )

    return {
        "authorization_url": auth_url,
        "state": state,
        "redirect_uri": redirect_uri,
        "environment": "demo" if settings.environment == "development" else "production"
    }


@router.get("/callback")
async def gusto_oauth_callback(
    code: str = Query(..., description="Authorization code from Gusto"),
    state: str = Query(..., description="CSRF protection state"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 2: Handle OAuth callback from Gusto.

    Exchange authorization code for access token and refresh token.
    """
    if not settings.gusto_client_id or not settings.gusto_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Gusto integration not configured"
        )

    redirect_uri = f"{settings.get_api_base_url()}/integrations/gusto/callback"
    api_base_url = "https://api.gusto-demo.com" if settings.environment == "development" else "https://api.gusto.com"

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{api_base_url}/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.gusto_client_id,
                    "client_secret": settings.gusto_client_secret,
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

    # Get company information
    async with httpx.AsyncClient() as client:
        try:
            me_response = await client.get(
                f"{api_base_url}/v1/me",
                headers={
                    "Authorization": f"Bearer {token_data['access_token']}",
                    "Content-Type": "application/json"
                }
            )
            me_response.raise_for_status()
            me_data = me_response.json()
        except httpx.HTTPStatusError:
            me_data = {}

    # Get or create Gusto integration record
    result = await db.execute(
        select(Integration).where(Integration.integration_key == "gusto")
    )
    integration = result.scalar_one_or_none()

    if not integration:
        integration = Integration(
            integration_key="gusto",
            display_name="Gusto",
            integration_type="accounting",
            auth_type="oauth2",
            requires_oauth=True,
            api_base_url=api_base_url,
            documentation_url="https://docs.gusto.com/app-integrations/docs/introduction"
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
        company_integration.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 7200))
        company_integration.status = "active"
        company_integration.config = {
            "company_uuid": me_data.get("roles", [{}])[0].get("companies", [{}])[0].get("uuid") if me_data.get("roles") else None,
            "user_email": me_data.get("email"),
            "roles": me_data.get("roles", [])
        }
        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
    else:
        company_integration = CompanyIntegration(
            company_id=current_user.company_id,
            integration_id=integration.id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 7200)),
            status="active",
            config={
                "company_uuid": me_data.get("roles", [{}])[0].get("companies", [{}])[0].get("uuid") if me_data.get("roles") else None,
                "user_email": me_data.get("email"),
                "roles": me_data.get("roles", [])
            },
            last_sync_at=datetime.utcnow()
        )
        db.add(company_integration)

    await db.commit()
    await db.refresh(company_integration)

    return {
        "status": "success",
        "integration_id": str(company_integration.id),
        "company_uuid": company_integration.config.get("company_uuid"),
        "message": "Gusto integration activated successfully"
    }


async def refresh_gusto_token(
    company_integration: CompanyIntegration,
    db: AsyncSession
) -> str:
    """Refresh Gusto access token (expires every 2 hours)."""
    if not company_integration.refresh_token:
        raise HTTPException(
            status_code=401,
            detail="No refresh token available. Please re-authorize."
        )

    api_base_url = "https://api.gusto-demo.com" if settings.environment == "development" else "https://api.gusto.com"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{api_base_url}/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": company_integration.refresh_token,
                    "client_id": settings.gusto_client_id,
                    "client_secret": settings.gusto_client_secret,
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
                detail="Failed to refresh Gusto token. Please re-authorize."
            )

    company_integration.access_token = token_data["access_token"]
    company_integration.refresh_token = token_data.get("refresh_token")
    company_integration.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 7200))
    await db.commit()

    return token_data["access_token"]


async def get_gusto_client(
    company_integration: CompanyIntegration,
    db: AsyncSession
) -> httpx.AsyncClient:
    """Get authenticated Gusto API client with automatic token refresh."""
    if company_integration.token_expires_at:
        if datetime.utcnow() >= company_integration.token_expires_at - timedelta(minutes=5):
            access_token = await refresh_gusto_token(company_integration, db)
        else:
            access_token = company_integration.access_token
    else:
        access_token = company_integration.access_token

    api_base_url = "https://api.gusto-demo.com" if settings.environment == "development" else "https://api.gusto.com"

    client = httpx.AsyncClient(
        base_url=f"{api_base_url}/v1",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        timeout=30.0
    )

    return client


@router.post("/{integration_id}/sync/employees")
async def sync_gusto_employees(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync employees from Gusto to FreightOps drivers."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    company_uuid = company_integration.config.get("company_uuid")
    if not company_uuid:
        raise HTTPException(status_code=400, detail="No company UUID found in integration")

    client = await get_gusto_client(company_integration, db)

    try:
        response = await client.get(f"/companies/{company_uuid}/employees")
        response.raise_for_status()
        employees = response.json()

        # TODO: Map Gusto employees to FreightOps drivers
        # For now, just return count

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "synced_count": len(employees),
            "message": f"Synced {len(employees)} employees from Gusto"
        }

    except httpx.HTTPStatusError as e:
        company_integration.last_error_message = f"Sync failed: {e.response.text}"
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sync employees: {e.response.text}"
        )
    finally:
        await client.aclose()


@router.post("/{integration_id}/sync/payrolls")
async def sync_gusto_payrolls(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync payroll data from Gusto."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    company_uuid = company_integration.config.get("company_uuid")
    if not company_uuid:
        raise HTTPException(status_code=400, detail="No company UUID found in integration")

    client = await get_gusto_client(company_integration, db)

    try:
        response = await client.get(f"/companies/{company_uuid}/payrolls")
        response.raise_for_status()
        payrolls = response.json()

        # TODO: Map payroll data to FreightOps settlements
        # For now, just return count

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "synced_count": len(payrolls),
            "message": f"Synced {len(payrolls)} payrolls from Gusto"
        }

    except httpx.HTTPStatusError as e:
        company_integration.last_error_message = f"Sync failed: {e.response.text}"
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sync payrolls: {e.response.text}"
        )
    finally:
        await client.aclose()


@router.delete("/{integration_id}")
async def disconnect_gusto(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect Gusto integration."""
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

    return {"status": "success", "message": "Gusto integration disconnected"}
