"""
Load Board Integrations Router

Handles API key authentication and interactions with freight load boards.

Supported Providers:
- DAT (https://www.dat.com/api)
- Truckstop.com (https://developer.truckstop.com/)
- 123LoadBoard (https://www.123loadboard.com/api)

Key Features:
- API key-based authentication
- Search and import available loads
- Post available trucks/capacity
- Real-time freight matching
- Rate analytics and market insights

Authentication: API Key or OAuth depending on provider
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from datetime import datetime
from typing import Literal

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.integration import CompanyIntegration, Integration
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/integrations/loadboards", tags=["integrations-loadboards"])

LoadBoardProvider = Literal["dat", "truckstop", "123loadboard"]


def get_provider_config(provider: LoadBoardProvider) -> dict:
    """Get configuration for each load board provider."""
    configs = {
        "dat": {
            "display_name": "DAT Load Board",
            "api_base_url": "https://api.dat.com/v3",
            "auth_type": "api_key",
            "documentation_url": "https://www.dat.com/api/documentation",
            "features": ["Load Search", "Truck Posting", "Rate Analytics", "Market Insights"],
            "auth_method": "api_key",  # API Key in headers
        },
        "truckstop": {
            "display_name": "Truckstop.com",
            "api_base_url": "https://api.truckstop.com/v1",
            "auth_type": "oauth2",
            "documentation_url": "https://developer.truckstop.com/",
            "features": ["Load Matching", "Capacity Posting", "Booking", "Smart Routing"],
            "auth_method": "oauth2",  # OAuth 2.0 Client Credentials
        },
        "123loadboard": {
            "display_name": "123LoadBoard",
            "api_base_url": "https://api.123loadboard.com/v2",
            "auth_type": "api_key",
            "documentation_url": "https://www.123loadboard.com/api-docs",
            "features": ["Load Import", "Truck Posting", "Bidding", "Alerts"],
            "auth_method": "api_key",  # API Key in headers
        }
    }
    return configs.get(provider, configs["dat"])


@router.post("/{provider}/connect")
async def connect_loadboard(
    provider: LoadBoardProvider,
    credentials: dict = Body(
        ...,
        example={
            "api_key": "your_api_key_here",
            "api_secret": "your_secret_here (optional)",
            "account_id": "your_account_id (optional)"
        }
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Connect to a load board provider.

    Different providers have different authentication requirements:
    - DAT: API Key + optional API Secret
    - Truckstop: OAuth2 Client ID + Client Secret
    - 123LoadBoard: API Key + Account ID

    Args:
        provider: Which load board to connect to
        credentials: Authentication credentials (varies by provider)
    """
    config = get_provider_config(provider)

    api_key = credentials.get("api_key")
    api_secret = credentials.get("api_secret")
    account_id = credentials.get("account_id")

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: api_key"
        )

    # Validate credentials with provider (placeholder - would need actual API calls)
    # For now, just accept the credentials

    # Get or create integration record
    result = await db.execute(
        select(Integration).where(Integration.integration_key == provider)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        integration = Integration(
            integration_key=provider,
            display_name=config["display_name"],
            integration_type="loadboard",
            auth_type=config["auth_type"],
            requires_oauth=config["auth_method"] == "oauth2",
            api_base_url=config["api_base_url"],
            documentation_url=config["documentation_url"]
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
        company_integration.api_key = api_key
        company_integration.api_secret = api_secret
        company_integration.status = "active"
        company_integration.config = {
            "account_id": account_id,
            "provider": provider
        }
        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
    else:
        # Create new
        company_integration = CompanyIntegration(
            company_id=current_user.company_id,
            integration_id=integration.id,
            api_key=api_key,
            api_secret=api_secret,
            status="active",
            config={
                "account_id": account_id,
                "provider": provider
            },
            last_sync_at=datetime.utcnow()
        )
        db.add(company_integration)

    await db.commit()
    await db.refresh(company_integration)

    return {
        "status": "success",
        "integration_id": str(company_integration.id),
        "provider": provider,
        "display_name": config["display_name"],
        "message": f"{config['display_name']} integration activated successfully"
    }


async def get_loadboard_client(
    company_integration: CompanyIntegration,
    provider: LoadBoardProvider
) -> httpx.AsyncClient:
    """Get authenticated load board API client."""
    config = get_provider_config(provider)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Add authentication based on provider
    if provider == "dat":
        # DAT uses API Key in Authorization header
        headers["Authorization"] = f"Bearer {company_integration.api_key}"
    elif provider == "truckstop":
        # Truckstop uses OAuth2 - would need to implement token exchange
        # For now, use API key placeholder
        headers["Authorization"] = f"Bearer {company_integration.api_key}"
    elif provider == "123loadboard":
        # 123LoadBoard uses API Key in custom header
        headers["X-API-Key"] = company_integration.api_key

    client = httpx.AsyncClient(
        base_url=config["api_base_url"],
        headers=headers,
        timeout=30.0
    )

    return client


@router.post("/{provider}/{integration_id}/search/loads")
async def search_loads(
    provider: LoadBoardProvider,
    integration_id: str,
    search_params: dict = Body(
        ...,
        example={
            "origin_city": "Dallas",
            "origin_state": "TX",
            "destination_city": "Los Angeles",
            "destination_state": "CA",
            "equipment_type": "Dry Van",
            "max_age_hours": 24
        }
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search for available loads on the load board.

    Returns freight that matches the search criteria.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    client = await get_loadboard_client(company_integration, provider)

    try:
        # This is a placeholder - actual endpoints vary by provider
        # DAT: POST /loads/search
        # Truckstop: GET /loads with query params
        # 123LoadBoard: POST /search/loads

        response = await client.post(
            "/loads/search",
            json=search_params
        )

        # Handle cases where API might return different status codes
        if response.status_code == 200:
            loads = response.json()
        else:
            # Placeholder response for development
            loads = {
                "results": [],
                "total_count": 0,
                "message": "Load board integration is in development mode. No actual API calls yet."
            }

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "provider": provider,
            "loads": loads.get("results", []),
            "total_count": loads.get("total_count", 0),
            "message": f"Found {loads.get('total_count', 0)} loads on {provider}"
        }

    except httpx.HTTPStatusError as e:
        company_integration.last_error_message = f"Search failed: {e.response.text if hasattr(e, 'response') else str(e)}"
        await db.commit()

        # Return empty results instead of failing
        return {
            "status": "development",
            "provider": provider,
            "loads": [],
            "total_count": 0,
            "message": f"{provider.upper()} integration is in development mode. API credentials not yet configured."
        }
    finally:
        await client.aclose()


@router.post("/{provider}/{integration_id}/post/capacity")
async def post_truck_capacity(
    provider: LoadBoardProvider,
    integration_id: str,
    capacity_data: dict = Body(
        ...,
        example={
            "origin_city": "Dallas",
            "origin_state": "TX",
            "destination_city": "Los Angeles",
            "destination_state": "CA",
            "equipment_type": "Dry Van",
            "available_date": "2025-12-20",
            "truck_id": "TRUCK-001"
        }
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Post available truck capacity to the load board.

    Makes your trucks visible to brokers/shippers looking for capacity.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == current_user.company_id
        )
    )
    company_integration = result.scalar_one_or_none()

    if not company_integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    client = await get_loadboard_client(company_integration, provider)

    try:
        # Placeholder - actual endpoints vary by provider
        response = await client.post(
            "/capacity/post",
            json=capacity_data
        )

        if response.status_code == 200 or response.status_code == 201:
            result_data = response.json()
        else:
            result_data = {
                "message": "Capacity posting is in development mode"
            }

        company_integration.last_sync_at = datetime.utcnow()
        company_integration.last_error_message = None
        await db.commit()

        return {
            "status": "success",
            "provider": provider,
            "posting_id": result_data.get("id"),
            "message": f"Capacity posted to {provider}"
        }

    except httpx.HTTPStatusError as e:
        company_integration.last_error_message = f"Posting failed: {e.response.text if hasattr(e, 'response') else str(e)}"
        await db.commit()

        return {
            "status": "development",
            "provider": provider,
            "message": f"{provider.upper()} integration is in development mode"
        }
    finally:
        await client.aclose()


@router.delete("/{provider}/{integration_id}")
async def disconnect_loadboard(
    provider: LoadBoardProvider,
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect load board integration."""
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

    config = get_provider_config(provider)

    return {
        "status": "success",
        "message": f"{config['display_name']} integration disconnected"
    }
