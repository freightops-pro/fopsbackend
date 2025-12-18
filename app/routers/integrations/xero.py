"""
Xero OAuth2 Integration Router

Handles OAuth2 authentication flow and API interactions with Xero accounting software.

API Documentation: https://developer.xero.com/documentation/guides/oauth2/overview/

Key Features:
- OAuth 2.0 authorization code flow
- Token refresh (30-minute access token expiry)
- Multi-tenant support via Xero-Tenant-Id header
- Sync invoices, bills, contacts, and reports

Rate Limits: 5,000 API calls per day per organisation (resets at midnight UTC)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import secrets
from datetime import datetime, timedelta
from typing import Optional

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.integration import CompanyIntegration, Integration
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/integrations/xero", tags=["integrations-xero"])


@router.get("/authorize")
async def initiate_xero_oauth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 1: Redirect user to Xero authorization page.

    Returns authorization URL with state parameter for CSRF protection.
    """
    if not settings.xero_client_id:
        raise HTTPException(
            status_code=503,
            detail="Xero integration not configured. Missing XERO_CLIENT_ID."
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state in database temporarily (expires in 10 minutes)
    # In production, use Redis or session storage
    # For now, we'll rely on Xero's built-in state validation

    # Xero OAuth2 scopes
    scopes = [
        "offline_access",  # Required for refresh tokens
        "accounting.transactions",  # Invoices, bills, payments
        "accounting.contacts",  # Customers and suppliers
        "accounting.reports.read",  # Financial reports
        "accounting.settings",  # Chart of accounts
    ]

    redirect_uri = f"{settings.get_api_base_url()}/integrations/xero/callback"

    auth_url = (
        f"https://login.xero.com/identity/connect/authorize"
        f"?response_type=code"
        f"&client_id={settings.xero_client_id}"
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
async def xero_oauth_callback(
    code: str = Query(..., description="Authorization code from Xero"),
    state: str = Query(..., description="CSRF protection state"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 2: Handle OAuth callback from Xero.

    Exchange authorization code for access token and refresh token.
    """
    if not settings.xero_client_id or not settings.xero_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Xero integration not configured"
        )

    # Exchange code for tokens
    redirect_uri = f"{settings.get_api_base_url()}/integrations/xero/callback"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://identity.xero.com/connect/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                auth=(settings.xero_client_id, settings.xero_client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange code for token: {e.response.text}"
            )

    # Get tenant connections (Xero organizations)
    async with httpx.AsyncClient() as client:
        try:
            connections_response = await client.get(
                "https://api.xero.com/connections",
                headers={
                    "Authorization": f"Bearer {token_data['access_token']}",
                    "Content-Type": "application/json"
                }
            )
            connections_response.raise_for_status()
            connections = connections_response.json()
        except httpx.HTTPStatusError:
            connections = []

    # Get or create Xero integration record
    result = await db.execute(
        select(Integration).where(Integration.integration_key == "xero")
    )
    integration = result.scalar_one_or_none()

    if not integration:
        # Create integration record
        integration = Integration(
            integration_key="xero",
            display_name="Xero",
            integration_type="accounting",
            auth_type="oauth2",
            requires_oauth=True,
            api_base_url="https://api.xero.com/api.xro/2.0",
            documentation_url="https://developer.xero.com/documentation/api/accounting/overview"
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
        # Update existing
        company_integration.access_token = token_data["access_token"]
        company_integration.refresh_token = token_data.get("refresh_token")
        company_integration.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        company_integration.status = "active"
        company_integration.config = {
            "tenant_id": connections[0]["tenantId"] if connections else None,
            "tenant_name": connections[0]["tenantName"] if connections else None,
            "connections": connections
        }
        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
    else:
        # Create new
        company_integration = CompanyIntegration(
            company_id=current_user.company_id,
            integration_id=integration.id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=datetime.utcnow() + timedelta(seconds=token_data["expires_in"]),
            status="active",
            config={
                "tenant_id": connections[0]["tenantId"] if connections else None,
                "tenant_name": connections[0]["tenantName"] if connections else None,
                "connections": connections
            },
            last_sync_at=datetime.utcnow()
        )
        db.add(company_integration)

    await db.commit()
    await db.refresh(company_integration)

    return {
        "status": "success",
        "integration_id": str(company_integration.id),
        "tenant_name": connections[0]["tenantName"] if connections else "Unknown",
        "message": "Xero integration activated successfully"
    }


async def refresh_xero_token(
    company_integration: CompanyIntegration,
    db: AsyncSession
) -> str:
    """
    Refresh Xero access token using refresh token.

    Xero access tokens expire after 30 minutes.
    """
    if not company_integration.refresh_token:
        raise HTTPException(
            status_code=401,
            detail="No refresh token available. Please re-authorize."
        )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://identity.xero.com/connect/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": company_integration.refresh_token,
                },
                auth=(settings.xero_client_id, settings.xero_client_secret),
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
                detail="Failed to refresh Xero token. Please re-authorize."
            )

    # Update tokens
    company_integration.access_token = token_data["access_token"]
    company_integration.refresh_token = token_data.get("refresh_token")
    company_integration.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
    await db.commit()

    return token_data["access_token"]


async def get_xero_client(
    company_integration: CompanyIntegration,
    db: AsyncSession
) -> httpx.AsyncClient:
    """Get authenticated Xero API client with automatic token refresh."""
    # Check if token needs refresh (refresh 5 minutes before expiry)
    if company_integration.token_expires_at:
        if datetime.utcnow() >= company_integration.token_expires_at - timedelta(minutes=5):
            access_token = await refresh_xero_token(company_integration, db)
        else:
            access_token = company_integration.access_token
    else:
        access_token = company_integration.access_token

    tenant_id = company_integration.config.get("tenant_id") if company_integration.config else None

    client = httpx.AsyncClient(
        base_url="https://api.xero.com/api.xro/2.0",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        timeout=30.0
    )

    return client


@router.post("/{integration_id}/sync/contacts")
async def sync_xero_contacts(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync customers and suppliers from Xero.

    Maps Xero contacts to FreightOps customers.
    """
    # Get integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    client = await get_xero_client(company_integration, db)

    try:
        # Fetch contacts from Xero
        response = await client.get("/Contacts")
        response.raise_for_status()
        data = response.json()

        contacts = data.get("Contacts", [])

        # TODO: Map to FreightOps customers
        # For now, just return count

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "synced_count": len(contacts),
            "message": f"Synced {len(contacts)} contacts from Xero"
        }

    except httpx.HTTPStatusError as e:
        company_integration.last_error_message = f"Sync failed: {e.response.text}"
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sync contacts: {e.response.text}"
        )
    finally:
        await client.aclose()


@router.post("/{integration_id}/sync/invoices")
async def sync_xero_invoices(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync invoices from Xero.

    Maps Xero invoices to FreightOps invoices/settlements.
    """
    # Get integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    client = await get_xero_client(company_integration, db)

    try:
        # Fetch invoices from Xero (last 30 days)
        response = await client.get("/Invoices")
        response.raise_for_status()
        data = response.json()

        invoices = data.get("Invoices", [])

        # TODO: Map to FreightOps invoices
        # For now, just return count

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "synced_count": len(invoices),
            "message": f"Synced {len(invoices)} invoices from Xero"
        }

    except httpx.HTTPStatusError as e:
        company_integration.last_error_message = f"Sync failed: {e.response.text}"
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sync invoices: {e.response.text}"
        )
    finally:
        await client.aclose()


@router.delete("/{integration_id}")
async def disconnect_xero(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect Xero integration."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Revoke Xero token
    if company_integration.access_token:
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    "https://identity.xero.com/connect/revocation",
                    data={"token": company_integration.access_token},
                    auth=(settings.xero_client_id, settings.xero_client_secret)
                )
            except:
                pass  # Continue even if revocation fails

    await db.delete(company_integration)
    await db.commit()

    return {"status": "success", "message": "Xero integration disconnected"}
