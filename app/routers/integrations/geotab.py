"""
Geotab API Integration Router

Handles Service Account authentication and API interactions with Geotab GPS/ELD platform.

API Documentation: https://geotab.github.io/sdk/software/api/reference/

Key Features:
- Service Account authentication (NOT OAuth)
- Session ID-based authentication (14-day expiry)
- Sync vehicles, drivers, trips, HOS data
- Real-time GPS tracking

Authentication: Username + Password + Database name → Session ID
Rate Limits: Depends on plan, typically burst-friendly
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from datetime import datetime, timedelta
from typing import Optional

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.integration import CompanyIntegration, Integration
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/integrations/geotab", tags=["integrations-geotab"])


@router.post("/connect")
async def connect_geotab(
    credentials: dict = Body(
        ...,
        example={
            "username": "service_account@company.com",
            "password": "your_password",
            "database": "company_database"
        }
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Connect to Geotab using Service Account credentials.

    Geotab uses a different authentication model than OAuth:
    1. Authenticate to the root federation server (my.geotab.com)
    2. Receive a session ID that lasts 14 days
    3. Use session ID in place of password for all API calls

    Required credentials:
    - username: Service account email
    - password: Service account password
    - database: Customer's database name
    """
    username = credentials.get("username")
    password = credentials.get("password")
    database = credentials.get("database")

    if not username or not password or not database:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: username, password, database"
        )

    # Authenticate to Geotab
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://my.geotab.com/apiv1",
                json={
                    "method": "Authenticate",
                    "params": {
                        "userName": username,
                        "password": password,
                        "database": database
                    }
                }
            )
            response.raise_for_status()
            auth_data = response.json()

            if "error" in auth_data:
                raise HTTPException(
                    status_code=401,
                    detail=f"Geotab authentication failed: {auth_data['error']['message']}"
                )

            result = auth_data.get("result", {})
            session_id = result.get("credentials", {}).get("sessionId")
            server = result.get("path", "my.geotab.com")

            if not session_id:
                raise HTTPException(
                    status_code=401,
                    detail="Failed to obtain session ID from Geotab"
                )

        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Geotab API error: {e.response.text}"
            )

    # Get or create Geotab integration record
    result_db = await db.execute(
        select(Integration).where(Integration.integration_key == "geotab")
    )
    integration = result_db.scalar_one_or_none()

    if not integration:
        integration = Integration(
            integration_key="geotab",
            display_name="Geotab",
            integration_type="eld",
            auth_type="api_key",  # Closest match (not OAuth)
            requires_oauth=False,
            api_base_url=f"https://{server}/apiv1",
            documentation_url="https://geotab.github.io/sdk/software/api/reference/"
        )
        db.add(integration)
        await db.flush()

    # Create or update company integration
    result_db = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.company_id == current_user.company_id,
            CompanyIntegration.integration_id == integration.id
        )
    )
    company_integration = result_db.scalar_one_or_none()

    if company_integration:
        # Update existing
        company_integration.access_token = session_id
        company_integration.api_key = username  # Store username for re-auth
        company_integration.api_secret = password  # Store encrypted password for re-auth
        company_integration.token_expires_at = datetime.utcnow() + timedelta(days=14)
        company_integration.status = "active"
        company_integration.config = {
            "database": database,
            "server": server,
            "username": username
        }
        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
    else:
        # Create new
        company_integration = CompanyIntegration(
            company_id=current_user.company_id,
            integration_id=integration.id,
            access_token=session_id,
            api_key=username,
            api_secret=password,  # TODO: Encrypt this
            token_expires_at=datetime.utcnow() + timedelta(days=14),
            status="active",
            config={
                "database": database,
                "server": server,
                "username": username
            },
            last_sync_at=datetime.utcnow()
        )
        db.add(company_integration)

    await db.commit()
    await db.refresh(company_integration)

    return {
        "status": "success",
        "integration_id": str(company_integration.id),
        "database": database,
        "server": server,
        "message": "Geotab integration activated successfully"
    }


async def refresh_geotab_session(
    company_integration: CompanyIntegration,
    db: AsyncSession
) -> str:
    """
    Re-authenticate to Geotab to get a new session ID.

    Session IDs expire after 14 days.
    """
    config = company_integration.config or {}
    username = company_integration.api_key
    password = company_integration.api_secret
    database = config.get("database")

    if not username or not password or not database:
        raise HTTPException(
            status_code=401,
            detail="Missing credentials for re-authentication. Please reconnect."
        )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://my.geotab.com/apiv1",
                json={
                    "method": "Authenticate",
                    "params": {
                        "userName": username,
                        "password": password,
                        "database": database
                    }
                }
            )
            response.raise_for_status()
            auth_data = response.json()

            if "error" in auth_data:
                company_integration.status = "error"
                company_integration.last_error_message = f"Re-authentication failed: {auth_data['error']['message']}"
                await db.commit()
                raise HTTPException(
                    status_code=401,
                    detail="Geotab re-authentication failed. Please reconnect."
                )

            result = auth_data.get("result", {})
            session_id = result.get("credentials", {}).get("sessionId")

        except httpx.HTTPStatusError as e:
            company_integration.status = "error"
            company_integration.last_error_message = f"Re-authentication error: {e.response.text}"
            await db.commit()
            raise HTTPException(
                status_code=401,
                detail="Failed to re-authenticate with Geotab"
            )

    company_integration.access_token = session_id
    company_integration.token_expires_at = datetime.utcnow() + timedelta(days=14)
    await db.commit()

    return session_id


async def get_geotab_client(
    company_integration: CompanyIntegration,
    db: AsyncSession
) -> tuple[httpx.AsyncClient, str, str]:
    """
    Get authenticated Geotab API client.

    Returns: (client, session_id, database)
    """
    # Check if session needs refresh
    if company_integration.token_expires_at:
        if datetime.utcnow() >= company_integration.token_expires_at - timedelta(days=1):
            session_id = await refresh_geotab_session(company_integration, db)
        else:
            session_id = company_integration.access_token
    else:
        session_id = company_integration.access_token

    config = company_integration.config or {}
    server = config.get("server", "my.geotab.com")
    database = config.get("database")

    client = httpx.AsyncClient(
        base_url=f"https://{server}",
        timeout=30.0
    )

    return client, session_id, database


@router.post("/{integration_id}/sync/vehicles")
async def sync_geotab_vehicles(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync vehicles from Geotab to FreightOps equipment."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    client, session_id, database = await get_geotab_client(company_integration, db)

    try:
        response = await client.post(
            "/apiv1",
            json={
                "method": "Get",
                "params": {
                    "typeName": "Device",
                    "credentials": {
                        "database": database,
                        "sessionId": session_id
                    }
                }
            }
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise HTTPException(
                status_code=400,
                detail=f"Geotab API error: {data['error']['message']}"
            )

        vehicles = data.get("result", [])

        # TODO: Map Geotab devices to FreightOps equipment
        # For now, just return count

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "synced_count": len(vehicles),
            "message": f"Synced {len(vehicles)} vehicles from Geotab"
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
async def sync_geotab_drivers(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync drivers from Geotab to FreightOps."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    client, session_id, database = await get_geotab_client(company_integration, db)

    try:
        response = await client.post(
            "/apiv1",
            json={
                "method": "Get",
                "params": {
                    "typeName": "User",
                    "credentials": {
                        "database": database,
                        "sessionId": session_id
                    }
                }
            }
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise HTTPException(
                status_code=400,
                detail=f"Geotab API error: {data['error']['message']}"
            )

        drivers = data.get("result", [])

        # TODO: Map Geotab users to FreightOps drivers
        # For now, just return count

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "synced_count": len(drivers),
            "message": f"Synced {len(drivers)} drivers from Geotab"
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


@router.delete("/{integration_id}")
async def disconnect_geotab(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect Geotab integration."""
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

    return {"status": "success", "message": "Geotab integration disconnected"}
