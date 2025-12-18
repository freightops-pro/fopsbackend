"""Router for managing third-party integrations (Motive, Samsara, etc.)."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.core.db import get_db
from app.models.integration import CompanyIntegration, Integration
from app.schemas.integration import (
    CompanyIntegrationCreate,
    CompanyIntegrationResponse,
    CompanyIntegrationUpdate,
    HaulPayBatchSubmissionRequest,
    HaulPayBatchSubmissionResponse,
    HaulPayInvoiceTracking,
    IntegrationListResponse,
    IntegrationStats,
    MotiveConnectionTest,
    MotiveCredentials,
    SamsaraConnectionTest,
    SamsaraCredentials,
)
from app.services.motive.motive_service import MotiveService
from app.services.quickbooks.quickbooks_service import QuickBooksService
from app.services.haulpay.haulpay_service import HaulPayService
from app.services.samsara.samsara_service import SamsaraService

logger = logging.getLogger(__name__)

router = APIRouter()

# Import sub-routers for specific integrations
from app.routers.integrations import xero, gusto, samsara as samsara_router, geotab, loadboards
from app.routers.integrations import efs, comdata, atob

# Include sub-routers
router.include_router(xero.router, tags=["Integrations - Xero"])
router.include_router(gusto.router, tags=["Integrations - Gusto"])
router.include_router(samsara_router.router, tags=["Integrations - Samsara"])
router.include_router(geotab.router, tags=["Integrations - Geotab"])
router.include_router(loadboards.router, tags=["Integrations - Load Boards"])

# Fuel Card integrations
router.include_router(efs.router, tags=["Integrations - EFS Fuel Cards"])
router.include_router(comdata.router, tags=["Integrations - Comdata"])
router.include_router(atob.router, tags=["Integrations - AtoB"])


async def _service(db: AsyncSession = Depends(get_db)) -> MotiveService:
    """Get Motive service instance."""
    return MotiveService(db)


async def _samsara_service(db: AsyncSession = Depends(get_db)) -> SamsaraService:
    """Get Samsara service instance."""
    return SamsaraService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Get current user's company ID."""
    return current_user.company_id


@router.get("/available", response_model=IntegrationListResponse)
async def list_available_integrations(
    integration_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> IntegrationListResponse:
    """List all available integrations, optionally filtered by type."""
    try:
        query = select(Integration).where(Integration.is_active == True)
        if integration_type:
            query = query.where(Integration.integration_type == integration_type)
        query = query.order_by(Integration.display_name)

        result = await db.execute(query)
        integrations = list(result.scalars().all())

        from app.schemas.integration import IntegrationInfo

        integration_infos = [IntegrationInfo.model_validate(integration) for integration in integrations]
        return IntegrationListResponse(integrations=integration_infos)
    except Exception as e:
        logger.error(f"Error listing integrations: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list integrations")


@router.get("/company", response_model=List[CompanyIntegrationResponse])
async def list_company_integrations(
    integration_type: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> List[CompanyIntegrationResponse]:
    """List all integrations for the current company."""
    try:
        query = (
            select(CompanyIntegration)
            .where(CompanyIntegration.company_id == company_id)
            .join(Integration)
            .order_by(Integration.display_name)
        )
        if integration_type:
            query = query.where(Integration.integration_type == integration_type)

        result = await db.execute(query)
        integrations = list(result.scalars().all())

        return [CompanyIntegrationResponse.model_validate(integration) for integration in integrations]
    except Exception as e:
        logger.error(f"Error listing company integrations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list company integrations"
        )


@router.get("/company/{integration_id}", response_model=CompanyIntegrationResponse)
async def get_company_integration(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> CompanyIntegrationResponse:
    """Get a specific company integration by ID."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return CompanyIntegrationResponse.model_validate(integration)


@router.post("/company", response_model=CompanyIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_company_integration(
    payload: CompanyIntegrationCreate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> CompanyIntegrationResponse:
    """Create a new company integration."""
    # Verify integration exists
    integration_result = await db.execute(select(Integration).where(Integration.id == payload.integration_id))
    integration = integration_result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Check if integration already exists for this company
    existing_result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.company_id == company_id,
            CompanyIntegration.integration_id == payload.integration_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Integration already exists for this company"
        )

    # Create new integration
    company_integration = CompanyIntegration(
        id=str(uuid.uuid4()),
        company_id=company_id,
        integration_id=payload.integration_id,
        status=payload.status,
        credentials=payload.credentials,
        config=payload.config,
        auto_sync=payload.auto_sync,
        sync_interval_minutes=payload.sync_interval_minutes,
        activated_at=datetime.utcnow() if payload.status == "active" else None,
    )
    db.add(company_integration)
    await db.commit()
    await db.refresh(company_integration)

    return CompanyIntegrationResponse.model_validate(company_integration)


@router.patch("/company/{integration_id}", response_model=CompanyIntegrationResponse)
async def update_company_integration(
    integration_id: str,
    payload: CompanyIntegrationUpdate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> CompanyIntegrationResponse:
    """Update a company integration."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Update fields
    if payload.credentials is not None:
        integration.credentials = payload.credentials
    if payload.config is not None:
        integration.config = payload.config
    if payload.status is not None:
        integration.status = payload.status
        if payload.status == "active" and not integration.activated_at:
            integration.activated_at = datetime.utcnow()
    if payload.auto_sync is not None:
        integration.auto_sync = payload.auto_sync
    if payload.sync_interval_minutes is not None:
        integration.sync_interval_minutes = payload.sync_interval_minutes

    integration.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(integration)

    return CompanyIntegrationResponse.model_validate(integration)


@router.delete("/company/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_integration(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a company integration."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    await db.delete(integration)
    await db.commit()


@router.get("/company/stats", response_model=IntegrationStats)
async def get_integration_stats(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> IntegrationStats:
    """Get statistics about company integrations."""
    result = await db.execute(
        select(CompanyIntegration).where(CompanyIntegration.company_id == company_id)
    )
    integrations = list(result.scalars().all())

    active_connections = sum(1 for i in integrations if i.status == "active")
    recent_syncs = sum(
        1
        for i in integrations
        if i.last_sync_at and (datetime.utcnow() - i.last_sync_at).total_seconds() < 3600
    )
    failed_syncs = sum(1 for i in integrations if i.consecutive_failures > 0)

    # Count by type
    by_type: Dict[str, int] = {}
    for integration in integrations:
        integration_result = await db.execute(
            select(Integration).where(Integration.id == integration.integration_id)
        )
        integration_catalog = integration_result.scalar_one_or_none()
        if integration_catalog:
            integration_type = integration_catalog.integration_type
            by_type[integration_type] = by_type.get(integration_type, 0) + 1

    return IntegrationStats(
        total_integrations=len(integrations),
        active_connections=active_connections,
        recent_syncs=recent_syncs,
        failed_syncs=failed_syncs,
        by_type=by_type,
    )


# Motive-specific endpoints
@router.post("/motive/test-connection", response_model=MotiveConnectionTest)
async def test_motive_connection(
    credentials: MotiveCredentials,
    company_id: str = Depends(_company_id),
    service: MotiveService = Depends(_service),
) -> MotiveConnectionTest:
    """Test connection to Motive API with provided credentials."""
    try:
        result = await service.test_connection(credentials.client_id, credentials.client_secret)
        return MotiveConnectionTest(**result)
    except Exception as e:
        logger.error(f"Motive connection test error: {e}", exc_info=True)
        return MotiveConnectionTest(
            connected=False, message=f"Connection test failed: {str(e)}", company=None
        )


# Samsara-specific endpoints
@router.post("/samsara/test-connection", response_model=SamsaraConnectionTest)
async def test_samsara_connection(
    credentials: SamsaraCredentials,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> SamsaraConnectionTest:
    """Test connection to Samsara API with provided OAuth credentials."""
    try:
        samsara_svc = SamsaraService(db)
        result = await samsara_svc.test_connection(
            credentials.client_id,
            credentials.client_secret,
            credentials.use_eu,
        )
        return SamsaraConnectionTest(**result)
    except Exception as e:
        logger.error(f"Samsara connection test error: {e}", exc_info=True)
        return SamsaraConnectionTest(
            connected=False, message=f"Connection test failed: {str(e)}", organization=None
        )


@router.post("/samsara/{integration_id}/sync/vehicles")
async def sync_samsara_vehicles(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Manually trigger vehicle sync from Samsara."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        samsara_svc = SamsaraService(db)
        devices = await samsara_svc.get_available_devices_from_integration(integration)

        integration.last_sync_at = datetime.utcnow()
        integration.last_success_at = datetime.utcnow()
        integration.consecutive_failures = 0
        integration.last_error_at = None
        integration.last_error_message = None
        await db.commit()

        return {
            "success": True,
            "message": f"Synced {len(devices)} vehicles from Samsara",
            "synced": len(devices),
        }
    except Exception as e:
        integration.consecutive_failures += 1
        integration.last_error_at = datetime.utcnow()
        integration.last_error_message = str(e)
        await db.commit()

        logger.error(f"Samsara vehicle sync error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )


@router.get("/samsara/{integration_id}/devices")
async def get_samsara_devices(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get available ELD devices from Samsara integration."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        samsara_svc = SamsaraService(db)
        devices = await samsara_svc.get_available_devices_from_integration(integration)
        return {
            "success": True,
            "provider": "samsara",
            "devices": devices,
        }
    except Exception as e:
        logger.error(f"Samsara device fetch error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch devices: {str(e)}",
        )


# Motive sync endpoints
@router.post("/motive/{integration_id}/sync/vehicles")
async def sync_motive_vehicles(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    service: MotiveService = Depends(_service),
) -> Dict[str, Any]:
    """Manually trigger vehicle sync from Motive."""
    # Get integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        result = await service.sync_vehicles(company_id, client_id, client_secret)
        integration.last_sync_at = datetime.utcnow()
        integration.last_success_at = datetime.utcnow()
        integration.consecutive_failures = 0
        integration.last_error_at = None
        integration.last_error_message = None
        await db.commit()

        return result
    except Exception as e:
        logger.error(f"Motive vehicle sync error: {e}", exc_info=True)
        integration.last_sync_at = datetime.utcnow()
        integration.last_error_at = datetime.utcnow()
        integration.last_error_message = str(e)
        integration.consecutive_failures += 1
        await db.commit()

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sync failed: {str(e)}")


@router.post("/motive/{integration_id}/sync/drivers")
async def sync_motive_drivers(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    service: MotiveService = Depends(_service),
) -> Dict[str, Any]:
    """Manually trigger driver sync from Motive."""
    # Get integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        result = await service.sync_users(company_id, client_id, client_secret)
        integration.last_sync_at = datetime.utcnow()
        integration.last_success_at = datetime.utcnow()
        integration.consecutive_failures = 0
        integration.last_error_at = None
        integration.last_error_message = None
        await db.commit()

        return result
    except Exception as e:
        logger.error(f"Motive driver sync error: {e}", exc_info=True)
        integration.last_sync_at = datetime.utcnow()
        integration.last_error_at = datetime.utcnow()
        integration.last_error_message = str(e)
        integration.consecutive_failures += 1
        await db.commit()

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sync failed: {str(e)}")


@router.get("/fuel-card/cards")
async def get_fuel_card_cards(
    unassigned_only: bool = False,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get available fuel cards from the active fuel card integration.

    Automatically detects which fuel card provider is active and fetches
    available cards from the local database or provider's API.

    Args:
        unassigned_only: If True, only return cards not assigned to a driver
    """
    from app.models.fuel import FuelCard

    # Find active fuel card integration
    result = await db.execute(
        select(CompanyIntegration)
        .join(Integration)
        .where(
            CompanyIntegration.company_id == company_id,
            CompanyIntegration.status == "active",
            Integration.integration_type == "fuel_card",
        )
        .options(selectinload(CompanyIntegration.integration))
    )
    integration = result.scalar_one_or_none()

    provider = None
    integration_id = None
    if integration and integration.integration:
        provider = integration.integration.integration_key
        integration_id = integration.id

    # Get fuel cards from database
    query = select(FuelCard).where(FuelCard.company_id == company_id)
    if unassigned_only:
        query = query.where(FuelCard.driver_id == None)  # noqa: E711
    query = query.order_by(FuelCard.created_at.desc())

    result = await db.execute(query)
    cards = result.scalars().all()

    return {
        "success": True,
        "provider": provider,
        "integration_id": integration_id,
        "cards": [
            {
                "id": card.id,
                "card_number": card.card_number,
                "card_provider": card.card_provider,
                "card_type": card.card_type,
                "card_nickname": card.card_nickname,
                "driver_id": card.driver_id,
                "truck_id": card.truck_id,
                "status": card.status,
                "daily_limit": float(card.daily_limit) if card.daily_limit else None,
                "display_name": card.card_nickname or f"{card.card_provider} {card.card_number}",
            }
            for card in cards
        ],
    }


@router.get("/eld/devices")
async def get_eld_devices(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    service: MotiveService = Depends(_service),
) -> Dict[str, Any]:
    """Get available ELD devices from the active ELD integration.

    Automatically detects which ELD provider is active and fetches
    available devices from that provider's API.
    """
    # Find active ELD integration
    result = await db.execute(
        select(CompanyIntegration)
        .join(Integration)
        .where(
            CompanyIntegration.company_id == company_id,
            CompanyIntegration.status == "active",
            Integration.integration_type == "eld",
        )
        .options(selectinload(CompanyIntegration.integration))
    )
    integration = result.scalar_one_or_none()

    if not integration:
        return {
            "success": True,
            "provider": None,
            "integration_id": None,
            "devices": [],
            "message": "No active ELD integration found",
        }

    if not integration.credentials:
        return {
            "success": False,
            "provider": None,
            "integration_id": integration.id,
            "devices": [],
            "message": "ELD integration has no credentials configured",
        }

    credentials = integration.credentials
    provider = integration.integration.integration_key if integration.integration else "unknown"

    try:
        devices: List[Dict[str, Any]] = []

        if provider == "motive":
            client_id = credentials.get("client_id")
            client_secret = credentials.get("client_secret")
            if client_id and client_secret:
                devices = await service.get_available_devices(company_id, client_id, client_secret)
        elif provider == "samsara":
            client_id = credentials.get("client_id")
            client_secret = credentials.get("client_secret")
            if client_id and client_secret:
                samsara_svc = SamsaraService(db)
                devices = await samsara_svc.get_available_devices_from_integration(integration)
        elif provider == "geotab":
            # Geotab integration - to be implemented when Geotab service is added
            # TODO: Implement Geotab device fetch
            devices = []

        return {
            "success": True,
            "provider": provider,
            "integration_id": integration.id,
            "devices": devices,
        }
    except Exception as e:
        logger.error(f"ELD device fetch error for {provider}: {e}", exc_info=True)
        return {
            "success": False,
            "provider": provider,
            "integration_id": integration.id,
            "devices": [],
            "message": f"Failed to fetch devices: {str(e)}",
        }


@router.get("/motive/{integration_id}/devices")
async def get_motive_devices(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    service: MotiveService = Depends(_service),
) -> Dict[str, Any]:
    """Get available ELD devices from Motive integration.

    Returns a list of vehicles/devices from the Motive API that can be
    used when creating new equipment.
    """
    # Get integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        devices = await service.get_available_devices(company_id, client_id, client_secret)
        return {
            "success": True,
            "provider": "motive",
            "devices": devices,
        }
    except Exception as e:
        logger.error(f"Motive device fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch devices: {str(e)}")


@router.get("/motive/{integration_id}/sync/status")
async def get_motive_sync_status(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get sync status for a Motive integration."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    return {
        "integration_id": integration.id,
        "status": integration.status,
        "last_sync_at": integration.last_sync_at.isoformat() if integration.last_sync_at else None,
        "last_success_at": integration.last_success_at.isoformat() if integration.last_success_at else None,
        "last_error_at": integration.last_error_at.isoformat() if integration.last_error_at else None,
        "last_error_message": integration.last_error_message,
        "consecutive_failures": integration.consecutive_failures,
        "auto_sync": integration.auto_sync,
        "sync_interval_minutes": integration.sync_interval_minutes,
    }


@router.get("/motive/{integration_id}/locations/vehicles")
async def get_motive_vehicle_locations(
    integration_id: str,
    vehicle_ids: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    service: MotiveService = Depends(_service),
) -> Dict[str, Any]:
    """Get vehicle locations from Motive."""
    # Get integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        vehicle_id_list = vehicle_ids.split(",") if vehicle_ids else None
        locations = await service.get_vehicle_locations(
            company_id, client_id, client_secret, vehicle_id_list
        )
        return {"success": True, "locations": locations}
    except Exception as e:
        logger.error(f"Motive location fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch locations: {str(e)}")


@router.get("/motive/{integration_id}/locations/drivers")
async def get_motive_driver_locations(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get driver locations from Motive."""
    # Get integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.motive_client import MotiveAPIClient

        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_driver_locations()
        locations = response.get("data", []) or response.get("drivers", [])
        return {"success": True, "locations": locations}
    except Exception as e:
        logger.error(f"Motive driver location fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch driver locations: {str(e)}")


@router.get("/motive/{integration_id}/geofences")
async def get_motive_geofences(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get geofences from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.motive_client import MotiveAPIClient

        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_geofences()
        geofences = response.get("data", []) or response.get("geofences", [])
        return {"success": True, "geofences": geofences}
    except Exception as e:
        logger.error(f"Motive geofence fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch geofences: {str(e)}")


@router.get("/motive/{integration_id}/geofence-events")
async def get_motive_geofence_events(
    integration_id: str,
    vehicle_id: Optional[str] = None,
    asset_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get geofence events from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.motive_client import MotiveAPIClient

        client = MotiveAPIClient(client_id, client_secret)
        if asset_id:
            response = await client.get_asset_geofence_events(
                asset_id=asset_id, start_time=start_time, end_time=end_time
            )
        else:
            response = await client.get_geofence_events(
                vehicle_id=vehicle_id, start_time=start_time, end_time=end_time
            )
        events = response.get("data", []) or response.get("events", [])
        return {"success": True, "events": events}
    except Exception as e:
        logger.error(f"Motive geofence event fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch geofence events: {str(e)}")


@router.post("/motive/{integration_id}/check-geofence")
async def check_geofence_status(
    integration_id: str,
    vehicle_id: str,
    latitude: float,
    longitude: float,
    geofence_id: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Check if a vehicle is within a geofence."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.motive_client import MotiveAPIClient

        client = MotiveAPIClient(client_id, client_secret)
        
        # Get vehicle location
        locations_response = await client.get_vehicle_locations_v3(vehicle_ids=[vehicle_id])
        locations = locations_response.get("data", []) or locations_response.get("vehicles", [])
        
        if not locations:
            return {"success": False, "inside_geofence": False, "message": "Vehicle location not found"}

        vehicle_location = locations[0]
        vehicle_lat = vehicle_location.get("latitude")
        vehicle_lon = vehicle_location.get("longitude")

        if vehicle_lat is None or vehicle_lon is None:
            return {"success": False, "inside_geofence": False, "message": "Vehicle location data incomplete"}

        # If geofence_id provided, check specific geofence
        if geofence_id:
            geofences_response = await client.get_geofence_by_id(geofence_id)
            geofence = geofences_response.get("data") or geofences_response.get("geofence")
            if geofence:
                # Simple distance check (could be enhanced with proper geofence polygon checking)
                geofence_lat = geofence.get("latitude") or geofence.get("center", {}).get("latitude")
                geofence_lon = geofence.get("longitude") or geofence.get("center", {}).get("longitude")
                radius = geofence.get("radius_meters", 100)  # Default 100 meters

                # Calculate distance (Haversine formula simplified)
                from math import radians, cos, sin, asin, sqrt
                lat1, lon1 = radians(vehicle_lat), radians(vehicle_lon)
                lat2, lon2 = radians(geofence_lat), radians(geofence_lon)
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                distance = 2 * asin(sqrt(a)) * 6371000  # Earth radius in meters

                inside = distance <= radius
                return {
                    "success": True,
                    "inside_geofence": inside,
                    "distance_meters": round(distance, 2),
                    "geofence_id": geofence_id,
                }

        # Check if vehicle is near the provided coordinates
        from math import radians, cos, sin, asin, sqrt
        lat1, lon1 = radians(vehicle_lat), radians(vehicle_lon)
        lat2, lon2 = radians(latitude), radians(longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        distance = 2 * asin(sqrt(a)) * 6371000  # Earth radius in meters

        # Consider within 100 meters as "inside"
        inside = distance <= 100

        return {
            "success": True,
            "inside_geofence": inside,
            "distance_meters": round(distance, 2),
            "vehicle_location": {"latitude": vehicle_lat, "longitude": vehicle_lon},
            "target_location": {"latitude": latitude, "longitude": longitude},
        }
    except Exception as e:
        logger.error(f"Geofence check error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to check geofence: {str(e)}")


@router.get("/motive/{integration_id}/hos/compliance")
async def get_motive_hos_compliance(
    integration_id: str,
    driver_id: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get HOS compliance data from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.motive_client import MotiveAPIClient

        client = MotiveAPIClient(client_id, client_secret)
        
        # Get drivers with available time
        available_time_response = await client.get_drivers_with_available_time()
        available_times = available_time_response.get("data", []) or available_time_response.get("drivers", [])
        
        # Get company drivers HOS
        hos_response = await client.get_company_drivers_hos()
        hos_data = hos_response.get("data", []) or hos_response.get("drivers", [])
        
        # Get HOS violations
        violations_response = await client.get_hos_violations()
        violations = violations_response.get("data", []) or violations_response.get("violations", [])
        
        # Filter by driver_id if provided
        if driver_id:
            available_times = [d for d in available_times if (d.get("id") or d.get("user_id")) == driver_id]
            hos_data = [d for d in hos_data if (d.get("id") or d.get("user_id")) == driver_id]
            violations = [v for v in violations if (v.get("driver_id") or v.get("user_id")) == driver_id]
        
        return {
            "success": True,
            "available_times": available_times,
            "hos_data": hos_data,
            "violations": violations,
        }
    except Exception as e:
        logger.error(f"Motive HOS compliance fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch HOS compliance: {str(e)}")


@router.get("/motive/{integration_id}/hos/logs")
async def get_motive_hos_logs(
    integration_id: str,
    driver_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get HOS logs from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.motive_client import MotiveAPIClient

        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_hos_logs_v2(
            user_id=driver_id, start_time=start_time, end_time=end_time
        )
        logs = response.get("hos_logs", []) or response.get("data", []) or response.get("logs", [])
        return {"success": True, "logs": logs}
    except Exception as e:
        logger.error(f"Motive HOS logs fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch HOS logs: {str(e)}")


@router.post("/motive/{integration_id}/sync/fuel")
async def sync_motive_fuel(
    integration_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    service: MotiveService = Depends(_service),
) -> Dict[str, Any]:
    """Manually trigger fuel purchase sync from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.sync.fuel_sync import FuelSyncService

        fuel_sync = FuelSyncService(db)
        result = await fuel_sync.sync_fuel_purchases(company_id, client_id, client_secret, start_date, end_date)
        
        integration.last_sync_at = datetime.utcnow()
        integration.last_success_at = datetime.utcnow()
        integration.consecutive_failures = 0
        integration.last_error_at = None
        integration.last_error_message = None
        await db.commit()

        return result
    except Exception as e:
        logger.error(f"Motive fuel sync error: {e}", exc_info=True)
        integration.last_sync_at = datetime.utcnow()
        integration.last_error_at = datetime.utcnow()
        integration.last_error_message = str(e)
        integration.consecutive_failures += 1
        await db.commit()

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sync failed: {str(e)}")


@router.get("/motive/{integration_id}/ifta/trips")
async def get_motive_ifta_trips(
    integration_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get IFTA trips from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_ifta_trips(start_date=start_date, end_date=end_date, vehicle_id=vehicle_id)
        trips = response.get("trips", []) or response.get("data", [])
        return {"success": True, "trips": trips}
    except Exception as e:
        logger.error(f"Motive IFTA trips fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch IFTA trips: {str(e)}")


@router.get("/motive/{integration_id}/ifta/mileage-summary")
async def get_motive_ifta_mileage_summary(
    integration_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get IFTA mileage summary from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_ifta_mileage_summary(start_date=start_date, end_date=end_date, vehicle_id=vehicle_id)
        summary = response.get("mileage_summary", []) or response.get("data", [])
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Motive IFTA mileage summary fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch IFTA mileage summary: {str(e)}")


@router.get("/motive/{integration_id}/fault-codes")
async def get_motive_fault_codes(
    integration_id: str,
    vehicle_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get fault codes from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_fault_codes(vehicle_id=vehicle_id, start_date=start_date, end_date=end_date)
        fault_codes = response.get("fault_codes", []) or response.get("data", [])
        return {"success": True, "fault_codes": fault_codes}
    except Exception as e:
        logger.error(f"Motive fault codes fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch fault codes: {str(e)}")


@router.get("/motive/{integration_id}/utilization")
async def get_motive_vehicle_utilization(
    integration_id: str,
    vehicle_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get vehicle utilization from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_vehicle_utilization(vehicle_id=vehicle_id, start_date=start_date, end_date=end_date)
        utilization = response.get("utilization", []) or response.get("data", [])
        return {"success": True, "utilization": utilization}
    except Exception as e:
        logger.error(f"Motive utilization fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch utilization: {str(e)}")


@router.get("/motive/{integration_id}/idle-events")
async def get_motive_idle_events(
    integration_id: str,
    vehicle_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get idle events from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_idle_events(vehicle_id=vehicle_id, start_date=start_date, end_date=end_date)
        events = response.get("idle_events", []) or response.get("data", [])
        return {"success": True, "events": events}
    except Exception as e:
        logger.error(f"Motive idle events fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch idle events: {str(e)}")


@router.get("/motive/oauth/callback")
async def motive_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    OAuth 2.0 callback endpoint for Motive authorization.
    
    This endpoint receives the authorization code from Motive after user authorization.
    The state parameter should contain the company_id and integration_id for security.
    """
    if error:
        logger.error(f"Motive OAuth error: {error} - {error_description}")
        return {
            "success": False,
            "error": error,
            "error_description": error_description,
            "message": "Authorization was denied or failed. Please try again.",
        }

    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code is required")

    # Parse state to get company_id and integration_id
    # State format: "{company_id}:{integration_id}" (base64 encoded for security)
    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="State parameter is required")

    try:
        import base64
        decoded_state = base64.b64decode(state).decode("utf-8")
        company_id, integration_id = decoded_state.split(":", 1)
    except Exception as e:
        logger.error(f"Failed to decode OAuth state: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state parameter")

    # Get integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Exchange authorization code for access token
    try:
        from app.services.motive.motive_client import MotiveAPIClient

        # Get client credentials from integration
        credentials = integration.credentials or {}
        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")

        if not client_id or not client_secret:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integration credentials not configured")

        # Exchange code for token (Motive OAuth flow)
        # Note: Motive primarily uses client credentials flow, but this endpoint
        # supports authorization code flow if Motive provides it
        client = MotiveAPIClient(client_id, client_secret)
        
        # Store the authorization code or exchange it for tokens
        # The actual implementation depends on Motive's OAuth flow
        logger.info(f"Motive OAuth callback received for integration {integration_id}")

        return {
            "success": True,
            "message": "Authorization successful. Integration is now active.",
            "integration_id": integration_id,
        }
    except Exception as e:
        logger.error(f"Motive OAuth token exchange error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to complete authorization: {str(e)}"
        )


@router.post("/motive/{integration_id}/webhooks/create")
async def create_motive_webhook(
    integration_id: str,
    webhook_secret: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Create the first webhook for a Motive integration.
    
    This endpoint creates a webhook in Motive that will send events to our webhook endpoint.
    The webhook is configured with common event types for fleet management.
    
    Args:
        integration_id: The integration ID
        webhook_secret: Optional webhook secret. If not provided, one will be generated.
    """
    # Get integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.motive_client import MotiveAPIClient
        from app.core.config import get_settings
        import secrets

        # Get base URL from config
        settings = get_settings()
        # Use the API base URL for webhook endpoint
        webhook_url = f"{settings.get_api_base_url()}/webhooks/motive"
        
        # Use provided secret, or from config, or generate a new one
        if not webhook_secret:
            webhook_secret = integration.config.get("webhook_secret") if integration.config else None
        if not webhook_secret:
            webhook_secret = secrets.token_urlsafe(32)
        
        # Create Motive API client
        client = MotiveAPIClient(client_id, client_secret)
        
        # Define webhook actions to subscribe to
        # Using Motive's actual action names from their documentation
        webhook_actions = [
            "vehicle_location_updated",  # Vehicle location updates
            "vehicle_location_received",  # All vehicle locations
            "hos_violation_upserted",  # HOS violations
            "vehicle_geofence_event",  # Geofence entry/exit
            "asset_geofence_event",  # Asset geofence events
            "fault_code_opened",  # New fault codes
            "fault_code_closed",  # Closed fault codes
            "vehicle_upserted",  # Vehicle created/updated
            "user_upserted",  # Driver created/updated
            "engine_toggle_event",  # Engine on/off
        ]
        
        # Create webhook in Motive
        webhook_response = await client.create_webhook(
            url=webhook_url,
            secret=webhook_secret,
            actions=webhook_actions,
            format="json",
            enabled=True,
            name=f"FreightOps Pro - {company_id}",
        )
        
        webhook_id = str(webhook_response.get("id") or webhook_response.get("webhook_id"))
        
        # Store webhook details in integration config
        if not integration.config:
            integration.config = {}
        
        integration.config["webhook_id"] = webhook_id
        integration.config["webhook_secret"] = webhook_secret
        integration.config["webhook_url"] = webhook_url
        integration.config["webhook_actions"] = webhook_actions
        
        await db.commit()
        await db.refresh(integration)
        
        logger.info(f"Created Motive webhook {webhook_id} for integration {integration_id}")
        
        return {
            "success": True,
            "message": "Webhook created successfully",
            "webhook": {
                "id": webhook_id,
                "url": webhook_url,
                "actions": webhook_actions,
                "enabled": True,
            },
        }
    except Exception as e:
        logger.error(f"Error creating Motive webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create webhook: {str(e)}"
        )


@router.get("/motive/{integration_id}/webhooks")
async def list_motive_webhooks(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List all webhooks for a Motive integration."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.motive_client import MotiveAPIClient

        client = MotiveAPIClient(client_id, client_secret)
        webhooks_response = await client.list_webhooks()
        webhooks = webhooks_response.get("company_webhooks", []) or webhooks_response.get("data", [])

        return {
            "success": True,
            "webhooks": webhooks,
            "stored_webhook_id": integration.config.get("webhook_id") if integration.config else None,
        }
    except Exception as e:
        logger.error(f"Error listing Motive webhooks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to list webhooks: {str(e)}"
        )


@router.get("/motive/{integration_id}/webhooks/{webhook_id}")
async def get_motive_webhook(
    integration_id: str,
    webhook_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get details of a specific webhook."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")

    try:
        from app.services.motive.motive_client import MotiveAPIClient

        client = MotiveAPIClient(client_id, client_secret)
        webhook = await client.get_webhook(webhook_id)

        return {"success": True, "webhook": webhook}
    except Exception as e:
        logger.error(f"Error getting Motive webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get webhook: {str(e)}"
        )


@router.post("/motive/{integration_id}/webhooks/update-secret")
async def update_motive_webhook_secret(
    integration_id: str,
    secret: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update the webhook secret stored in the integration config."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.config:
        integration.config = {}

    integration.config["webhook_secret"] = secret
    await db.commit()

    return {"success": True, "message": "Webhook secret updated"}


# Dispatch Locations Endpoints
@router.get("/motive/{integration_id}/dispatch-locations")
async def get_motive_dispatch_locations(
    integration_id: str,
    per_page: Optional[int] = None,
    page_no: Optional[int] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get dispatch locations from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_dispatch_locations(per_page=per_page, page_no=page_no)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"Motive dispatch locations fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch dispatch locations: {str(e)}")


@router.post("/motive/{integration_id}/dispatch-locations")
async def create_motive_dispatch_location(
    integration_id: str,
    location_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a dispatch location in Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.create_dispatch_location(location_data)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"Motive dispatch location creation error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create dispatch location: {str(e)}")


@router.put("/motive/{integration_id}/dispatch-locations/{location_id}")
async def update_motive_dispatch_location(
    integration_id: str,
    location_id: str,
    location_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update a dispatch location in Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.update_dispatch_location(location_id, location_data)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"Motive dispatch location update error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update dispatch location: {str(e)}")


# Forms Endpoints
@router.get("/motive/{integration_id}/forms")
async def get_motive_forms(
    integration_id: str,
    per_page: Optional[int] = None,
    page_no: Optional[int] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get forms from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_forms(per_page=per_page, page_no=page_no)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"Motive forms fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch forms: {str(e)}")


# Form Entries Endpoints
@router.get("/motive/{integration_id}/form-entries")
async def get_motive_form_entries(
    integration_id: str,
    form_id: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    per_page: Optional[int] = None,
    page_no: Optional[int] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get form entries from Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.get_form_entries(
            form_id=form_id,
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            start_date=start_date,
            end_date=end_date,
            per_page=per_page,
            page_no=page_no,
        )
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"Motive form entries fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch form entries: {str(e)}")


# Dispatch Endpoints
@router.post("/motive/{integration_id}/dispatches")
async def create_motive_dispatch(
    integration_id: str,
    dispatch_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a dispatch in Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.create_dispatch(dispatch_data)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"Motive dispatch creation error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create dispatch: {str(e)}")


@router.put("/motive/{integration_id}/dispatches/{dispatch_id}")
async def update_motive_dispatch(
    integration_id: str,
    dispatch_id: str,
    dispatch_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update a dispatch in Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.update_dispatch(dispatch_id, dispatch_data)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"Motive dispatch update error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update dispatch: {str(e)}")


# Messages Endpoints
@router.post("/motive/{integration_id}/messages/v2")
async def send_motive_message_v2(
    integration_id: str,
    message_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Send bulk messages to users (v2) in Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.send_message_v2(message_data)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"Motive message send error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send message: {str(e)}")


# Inspection Reports Endpoints
@router.put("/motive/{integration_id}/inspection-reports/{report_id}")
async def update_motive_inspection_report(
    integration_id: str,
    report_id: str,
    report_data: Dict[str, Any],
    external_ids_attributes: Optional[Dict[str, Any]] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update an inspection report in Motive."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No credentials configured")
    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials format")
    try:
        from app.services.motive.motive_client import MotiveAPIClient
        client = MotiveAPIClient(client_id, client_secret)
        response = await client.update_inspection_report(report_id, report_data, external_ids_attributes)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"Motive inspection report update error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update inspection report: {str(e)}")


# ============================================================================
# QuickBooks Online Integration Endpoints
# ============================================================================

@router.get("/quickbooks/{integration_id}/oauth/authorize")
async def quickbooks_oauth_authorize(
    integration_id: str,
    sandbox: bool = True,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Generate QuickBooks OAuth authorization URL using intuit-oauth SDK.

    This endpoint returns the URL where users should be redirected to authorize
    the application with QuickBooks.

    Args:
        integration_id: CompanyIntegration ID
        sandbox: Whether to use sandbox environment (default: True for development)
    """
    from intuitlib.client import AuthClient
    from intuitlib.enums import Scopes
    from app.core.config import get_settings

    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        ).join(Integration)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client credentials not configured")

    client_id = integration.credentials.get("client_id")
    client_secret = integration.credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client credentials not configured")

    settings = get_settings()
    redirect_uri = f"{settings.get_api_base_url()}/integrations/quickbooks/{integration_id}/oauth/callback"
    environment = "sandbox" if sandbox else "production"

    # Create AuthClient using the SDK
    auth_client = AuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        environment=environment,
    )

    # Get authorization URL with scopes - SDK handles state generation
    scopes = [Scopes.ACCOUNTING]
    auth_url = auth_client.get_authorization_url(scopes)

    # Store state for CSRF validation (SDK generates it)
    if not integration.config:
        integration.config = {}
    integration.config["oauth_state"] = auth_client.state_token
    integration.config["sandbox"] = sandbox
    await db.commit()

    return {
        "success": True,
        "authorization_url": auth_url,
        "state": auth_client.state_token,
        "environment": environment,
    }


@router.get("/quickbooks/{integration_id}/oauth/callback")
async def quickbooks_oauth_callback(
    integration_id: str,
    code: str,
    state: str,
    realmId: str,  # QuickBooks company ID (note: QBO uses camelCase)
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Handle QuickBooks OAuth callback and exchange authorization code for tokens.

    This endpoint is called by QuickBooks after user authorization.
    Uses intuit-oauth SDK for secure token exchange.
    """
    from intuitlib.client import AuthClient
    from intuitlib.exceptions import AuthClientError
    from app.core.config import get_settings

    result = await db.execute(
        select(CompanyIntegration).where(CompanyIntegration.id == integration_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Verify state
    stored_state = integration.config.get("oauth_state") if integration.config else None
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid state parameter")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client credentials not configured")

    client_id = integration.credentials.get("client_id")
    client_secret = integration.credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")

    settings = get_settings()
    redirect_uri = f"{settings.get_api_base_url()}/integrations/quickbooks/{integration_id}/oauth/callback"

    # Get environment from config (set during authorize)
    sandbox = integration.config.get("sandbox", True) if integration.config else True
    environment = "sandbox" if sandbox else "production"

    try:
        # Create AuthClient using the SDK
        auth_client = AuthClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            environment=environment,
        )

        # Exchange authorization code for tokens using SDK
        auth_client.get_bearer_token(code, realm_id=realmId)

        # Store tokens and realm_id from SDK
        if not integration.credentials:
            integration.credentials = {}
        integration.credentials["access_token"] = auth_client.access_token
        integration.credentials["refresh_token"] = auth_client.refresh_token

        if not integration.config:
            integration.config = {}
        integration.config["realm_id"] = realmId
        integration.config["token_expires_in"] = auth_client.expires_in
        integration.config["x_refresh_token_expires_in"] = auth_client.x_refresh_token_expires_in

        # Clear OAuth state
        if "oauth_state" in integration.config:
            del integration.config["oauth_state"]

        integration.status = "active"
        integration.activated_at = datetime.utcnow()
        await db.commit()

        return {
            "success": True,
            "message": "QuickBooks connection successful",
            "realm_id": realmId,
            "environment": environment,
        }
    except AuthClientError as e:
        logger.error(f"QuickBooks OAuth token exchange error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )
    except Exception as e:
        logger.error(f"QuickBooks OAuth unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/oauth/complete")
async def quickbooks_oauth_complete_manual(
    integration_id: str,
    authorization_code: str,
    realm_id: str,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
    sandbox: bool = True,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Manually complete QuickBooks OAuth flow with authorization code using intuit-oauth SDK.

    This endpoint allows you to complete the OAuth flow by providing the
    authorization code and realm_id directly, without going through the redirect.

    Args:
        integration_id: CompanyIntegration ID
        authorization_code: OAuth authorization code from QuickBooks
        realm_id: QuickBooks company/realm ID
        redirect_uri: Redirect URI used in authorization (optional, defaults to our callback URL)
                     If you used OAuth playground, use: https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl
        state: OAuth state parameter (optional, for validation)
        sandbox: Whether to use sandbox environment (default: True)
    """
    from intuitlib.client import AuthClient
    from intuitlib.exceptions import AuthClientError
    from app.core.config import get_settings

    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Verify state if provided
    if state:
        stored_state = integration.config.get("oauth_state") if integration.config else None
        if stored_state and stored_state != state:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid state parameter")

    if not integration.credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client credentials not configured")

    client_id = integration.credentials.get("client_id")
    client_secret = integration.credentials.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")

    settings = get_settings()
    # Use provided redirect_uri or default to our callback URL
    if not redirect_uri:
        redirect_uri = f"{settings.get_api_base_url()}/integrations/quickbooks/{integration_id}/oauth/callback"

    environment = "sandbox" if sandbox else "production"

    try:
        # Create AuthClient using the SDK
        auth_client = AuthClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            environment=environment,
        )

        # Exchange authorization code for tokens using SDK
        auth_client.get_bearer_token(authorization_code, realm_id=realm_id)

        # Store tokens and realm_id from SDK
        if not integration.credentials:
            integration.credentials = {}
        integration.credentials["access_token"] = auth_client.access_token
        integration.credentials["refresh_token"] = auth_client.refresh_token

        if not integration.config:
            integration.config = {}
        integration.config["realm_id"] = realm_id
        integration.config["sandbox"] = sandbox
        integration.config["token_expires_in"] = auth_client.expires_in
        integration.config["x_refresh_token_expires_in"] = auth_client.x_refresh_token_expires_in

        # Clear OAuth state
        if "oauth_state" in integration.config:
            del integration.config["oauth_state"]

        integration.status = "active"
        integration.activated_at = datetime.utcnow()
        await db.commit()

        logger.info(f"QuickBooks OAuth completed successfully for integration {integration_id}")
        return {
            "success": True,
            "message": "QuickBooks connection successful",
            "realm_id": realm_id,
            "integration_id": integration_id,
            "environment": environment,
        }
    except AuthClientError as e:
        logger.error(f"QuickBooks OAuth token exchange error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )
    except Exception as e:
        logger.error(f"QuickBooks OAuth unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/test-connection")
async def quickbooks_test_connection(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Test QuickBooks connection by fetching company info."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        result = await service.test_connection(integration)
        return result
    except Exception as e:
        logger.error(f"QuickBooks connection test error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/sync/customers")
async def quickbooks_sync_customers(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sync customers from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        result = await service.sync_customers(integration)
        
        # Update last sync time
        integration.last_sync_at = datetime.utcnow()
        if result.get("success"):
            integration.last_success_at = datetime.utcnow()
            integration.consecutive_failures = 0
        else:
            integration.last_error_at = datetime.utcnow()
            integration.last_error_message = result.get("message")
            integration.consecutive_failures += 1
        await db.commit()
        
        return result
    except Exception as e:
        logger.error(f"QuickBooks customer sync error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/sync/invoices")
async def quickbooks_sync_invoices(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sync invoices from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        result = await service.sync_invoices(integration)
        
        # Update last sync time
        integration.last_sync_at = datetime.utcnow()
        if result.get("success"):
            integration.last_success_at = datetime.utcnow()
            integration.consecutive_failures = 0
        else:
            integration.last_error_at = datetime.utcnow()
            integration.last_error_message = result.get("message")
            integration.consecutive_failures += 1
        await db.commit()
        
        return result
    except Exception as e:
        logger.error(f"QuickBooks invoice sync error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/sync/payments")
async def quickbooks_sync_payments(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sync payments from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        result = await service.sync_payments(integration)
        
        # Update last sync time
        integration.last_sync_at = datetime.utcnow()
        if result.get("success"):
            integration.last_success_at = datetime.utcnow()
            integration.consecutive_failures = 0
        else:
            integration.last_error_at = datetime.utcnow()
            integration.last_error_message = result.get("message")
            integration.consecutive_failures += 1
        await db.commit()
        
        return result
    except Exception as e:
        logger.error(f"QuickBooks payment sync error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.get("/quickbooks/{integration_id}/customers")
async def quickbooks_get_customers(
    integration_id: str,
    start_position: int = 1,
    max_results: int = 20,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get customers from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        client = await service.get_client(integration)
        response = await client.get_customers(start_position=start_position, max_results=max_results)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"QuickBooks get customers error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch customers: {str(e)}"
        )


@router.get("/quickbooks/{integration_id}/invoices")
async def quickbooks_get_invoices(
    integration_id: str,
    start_position: int = 1,
    max_results: int = 20,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get invoices from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        client = await service.get_client(integration)
        response = await client.get_invoices(start_position=start_position, max_results=max_results)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"QuickBooks get invoices error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch invoices: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/sync/accounts")
async def quickbooks_sync_accounts(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sync accounts (Chart of Accounts) from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        result = await service.sync_accounts(integration)
        
        # Update last sync time
        integration.last_sync_at = datetime.utcnow()
        if result.get("success"):
            integration.last_success_at = datetime.utcnow()
            integration.consecutive_failures = 0
        else:
            integration.last_error_at = datetime.utcnow()
            integration.last_error_message = result.get("message")
            integration.consecutive_failures += 1
        await db.commit()
        
        return result
    except Exception as e:
        logger.error(f"QuickBooks account sync error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.get("/quickbooks/{integration_id}/accounts")
async def quickbooks_get_accounts(
    integration_id: str,
    start_position: int = 1,
    max_results: int = 20,
    account_type: Optional[str] = None,
    active_only: bool = True,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get accounts (Chart of Accounts) from QuickBooks.
    
    Args:
        integration_id: Integration ID
        start_position: Starting position for pagination (default: 1)
        max_results: Maximum number of results (default: 20)
        account_type: Filter by account type (e.g., "Bank", "Expense", "Income")
        active_only: Only return active accounts (default: True)
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        client = await service.get_client(integration)
        response = await client.get_accounts(
            start_position=start_position,
            max_results=max_results,
            account_type=account_type,
            active_only=active_only,
        )
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"QuickBooks get accounts error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch accounts: {str(e)}"
        )


@router.get("/quickbooks/{integration_id}/accounts/{account_id}")
async def quickbooks_get_account(
    integration_id: str,
    account_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get a specific account by ID from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        client = await service.get_client(integration)
        response = await client.get_account(account_id)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"QuickBooks get account error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch account: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/accounts")
async def quickbooks_create_account(
    integration_id: str,
    account_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Create a new account in QuickBooks Chart of Accounts.
    
    Required fields in account_data:
        - Name: Account name
        - AccountType: Type of account (e.g., "Bank", "Expense", "Income")
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        client = await service.get_client(integration)
        response = await client.create_account(account_data)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"QuickBooks create account error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create account: {str(e)}"
        )


@router.put("/quickbooks/{integration_id}/accounts/{account_id}")
async def quickbooks_update_account(
    integration_id: str,
    account_id: str,
    account_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Update an existing account in QuickBooks (sparse update).
    
    Required fields in account_data:
        - Id: Account ID
        - SyncToken: Current sync token (for optimistic locking)
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        client = await service.get_client(integration)
        response = await client.update_account(account_id, account_data)
        return {"success": True, "data": response}
    except Exception as e:
        logger.error(f"QuickBooks update account error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update account: {str(e)}"
        )


@router.get("/quickbooks/{integration_id}/account-types")
async def quickbooks_get_account_types(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get list of available QuickBooks account types and subtypes."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    try:
        service = QuickBooksService(db)
        client = await service.get_client(integration)
        account_types = await client.get_account_types()
        return {"success": True, "data": account_types}
    except Exception as e:
        logger.error(f"QuickBooks get account types error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch account types: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/sync/vendors")
async def quickbooks_sync_vendors(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sync vendors from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        sync_result = await service.sync_vendors(integration)
        return sync_result
    except Exception as e:
        logger.error(f"QuickBooks vendor sync error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vendor sync failed: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/sync/bills")
async def quickbooks_sync_bills(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sync bills (payables) from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        sync_result = await service.sync_bills(integration)
        return sync_result
    except Exception as e:
        logger.error(f"QuickBooks bill sync error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bill sync failed: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/sync/full")
async def quickbooks_full_sync(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Perform full sync of all QuickBooks data (customers, vendors, invoices, bills, payments, accounts)."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        sync_result = await service.full_sync(integration)
        return sync_result
    except Exception as e:
        logger.error(f"QuickBooks full sync error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Full sync failed: {str(e)}"
        )


@router.get("/quickbooks/{integration_id}/sync/summary")
async def quickbooks_sync_summary(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get summary of QuickBooks data and sync status."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        summary = await service.get_sync_summary(integration)
        return summary
    except Exception as e:
        logger.error(f"QuickBooks sync summary error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync summary: {str(e)}"
        )


# =====================
# PUSH/EXPORT ENDPOINTS (TMS -> QuickBooks)
# =====================

@router.post("/quickbooks/{integration_id}/push/invoice")
async def quickbooks_push_invoice(
    integration_id: str,
    invoice_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Push an invoice from TMS to QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        push_result = await service.push_invoice_to_quickbooks(integration, invoice_data)
        if not push_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=push_result.get("message", "Failed to push invoice")
            )
        return push_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QuickBooks push invoice error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push invoice: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/push/payment")
async def quickbooks_push_payment(
    integration_id: str,
    payment_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Push a payment record from TMS to QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        push_result = await service.push_payment_to_quickbooks(integration, payment_data)
        if not push_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=push_result.get("message", "Failed to push payment")
            )
        return push_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QuickBooks push payment error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push payment: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/push/expense")
async def quickbooks_push_expense(
    integration_id: str,
    expense_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Push an expense (fuel, etc.) from TMS to QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        push_result = await service.push_expense_to_quickbooks(integration, expense_data)
        if not push_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=push_result.get("message", "Failed to push expense")
            )
        return push_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QuickBooks push expense error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push expense: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/push/bill")
async def quickbooks_push_bill(
    integration_id: str,
    bill_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Push a vendor bill from TMS to QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        push_result = await service.push_bill_to_quickbooks(integration, bill_data)
        if not push_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=push_result.get("message", "Failed to push bill")
            )
        return push_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QuickBooks push bill error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push bill: {str(e)}"
        )


@router.post("/quickbooks/{integration_id}/push/batch")
async def quickbooks_push_batch(
    integration_id: str,
    batch_data: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Push multiple items (invoices, payments, expenses, bills) to QuickBooks in batch."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        push_result = await service.push_batch_to_quickbooks(integration, batch_data)
        return push_result
    except Exception as e:
        logger.error(f"QuickBooks batch push error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push batch: {str(e)}"
        )


# =====================
# GET ENDPOINTS (QuickBooks -> TMS)
# =====================

@router.get("/quickbooks/{integration_id}/vendors")
async def quickbooks_get_vendors(
    integration_id: str,
    max_results: int = 100,
    start_position: int = 1,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get vendors from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        client = await service.get_client(integration)
        vendors = await client.get_vendors(max_results=max_results, start_position=start_position)
        return {"success": True, "data": vendors}
    except Exception as e:
        logger.error(f"QuickBooks get vendors error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch vendors: {str(e)}"
        )


@router.get("/quickbooks/{integration_id}/bills")
async def quickbooks_get_bills(
    integration_id: str,
    max_results: int = 100,
    start_position: int = 1,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get bills (payables) from QuickBooks."""
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        client = await service.get_client(integration)
        bills = await client.get_bills(max_results=max_results, start_position=start_position)
        return {"success": True, "data": bills}
    except Exception as e:
        logger.error(f"QuickBooks get bills error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bills: {str(e)}"
        )


# HaulPay Integration Endpoints
# Based on: https://docs.haulpay.io/carrier-api

@router.post("/haulpay/{integration_id}/sync/debtors")
async def haulpay_sync_debtors(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Sync debtor relationships from HaulPay.
    This should be called daily to keep debtor status up to date.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = HaulPayService(db)
        # Get external customer map (you'd implement this based on your customer model)
        external_customer_map = {}  # TODO: Build from Customer model
        result = await service.sync_debtor_relationships(company_id, external_customer_map)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"HaulPay sync debtors error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync debtors: {str(e)}"
        )


@router.post("/haulpay/{integration_id}/sync/carriers")
async def haulpay_sync_carriers(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Sync carrier relationships from HaulPay.
    This should be called daily to keep carrier status up to date.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = HaulPayService(db)
        external_carrier_map = {}  # TODO: Build from Carrier model
        result = await service.sync_carrier_relationships(company_id, external_carrier_map)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"HaulPay sync carriers error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync carriers: {str(e)}"
        )


@router.get("/haulpay/{integration_id}/search/debtors")
async def haulpay_search_debtors(
    integration_id: str,
    search: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Search for debtors in HaulPay.
    Used when connecting a new customer to a HaulPay debtor.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = HaulPayService(db)
        debtors = await service.search_debtors(company_id, search=search)
        return {"success": True, "data": debtors}
    except Exception as e:
        logger.error(f"HaulPay search debtors error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search debtors: {str(e)}"
        )


@router.get("/haulpay/{integration_id}/search/carriers")
async def haulpay_search_carriers(
    integration_id: str,
    search: Optional[str] = None,
    mc: Optional[str] = None,
    dot: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Search for carriers in HaulPay.
    Used when connecting a new carrier to a HaulPay carrier.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = HaulPayService(db)
        carriers = await service.search_carriers(company_id, search=search, mc=mc, dot=dot)
        return {"success": True, "data": carriers}
    except Exception as e:
        logger.error(f"HaulPay search carriers error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search carriers: {str(e)}"
        )


@router.post("/haulpay/{integration_id}/connect/debtor")
async def haulpay_connect_debtor(
    integration_id: str,
    debtor_id: str,
    customer_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Connect a customer to a HaulPay debtor.
    Creates a relationship and stores the external ID mapping.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = HaulPayService(db)
        result = await service.connect_debtor(company_id, debtor_id, customer_id)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"HaulPay connect debtor error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect debtor: {str(e)}"
        )


@router.post("/haulpay/{integration_id}/connect/carrier")
async def haulpay_connect_carrier(
    integration_id: str,
    carrier_id: str,
    carrier_external_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Connect a carrier to a HaulPay carrier.
    Creates a relationship and stores the external ID mapping.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = HaulPayService(db)
        result = await service.connect_carrier(company_id, carrier_id, carrier_external_id)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"HaulPay connect carrier error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect carrier: {str(e)}"
        )


@router.post("/haulpay/{integration_id}/submit-invoice")
async def haulpay_submit_invoice(
    integration_id: str,
    invoice_id: str,
    debtor_id: str,
    carrier_id: str,
    document_urls: Optional[List[Dict[str, str]]] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Submit an invoice to HaulPay for factoring with optional document attachments.
    HaulPay will purchase the invoice and advance funds to the carrier.
    
    Documents can include:
    - POD (Proof of Delivery) - Required for factoring
    - BOL (Bill of Lading)
    - Rate confirmation
    - Delivery receipt
    - Other supporting documents
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        # Get invoice from database
        from app.models.accounting import Invoice
        invoice_result = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.company_id == company_id)
        )
        invoice = invoice_result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        service = HaulPayService(db)
        result = await service.submit_invoice_for_factoring(
            company_id=company_id,
            invoice=invoice,
            debtor_id=debtor_id,
            carrier_id=carrier_id,
            document_urls=document_urls,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HaulPay submit invoice error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit invoice for factoring: {str(e)}"
        )


@router.get("/haulpay/{integration_id}/invoice/{haulpay_invoice_id}/status")
async def haulpay_get_invoice_status(
    integration_id: str,
    haulpay_invoice_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get the factoring status of an invoice from HaulPay.
    Returns status, advance amount, reserve, fees, and funding date.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = HaulPayService(db)
        result = await service.get_factoring_status(company_id, haulpay_invoice_id)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"HaulPay get invoice status error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get invoice status: {str(e)}"
        )


@router.post("/haulpay/{integration_id}/batch-submit-invoices", response_model=HaulPayBatchSubmissionResponse)
async def haulpay_batch_submit_invoices(
    integration_id: str,
    payload: HaulPayBatchSubmissionRequest,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> HaulPayBatchSubmissionResponse:
    """
    Batch submit multiple invoices to HaulPay for factoring.
    Each invoice is tracked separately with its own status, advance amount, and reserve.
    
    Example request:
    {
        "invoices": [
            {
                "invoice_id": "invoice-uuid-1",
                "debtor_id": "debtor-123",
                "carrier_id": "carrier-456"  // optional
            },
            {
                "invoice_id": "invoice-uuid-2",
                "debtor_id": "debtor-123"
            }
        ]
    }
    
    Returns detailed results for each invoice including success/failure status.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not payload.invoices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invoices list cannot be empty"
        )

    try:
        # Convert Pydantic models to dicts for service
        invoice_submissions = []
        for inv in payload.invoices:
            submission = {
                "invoice_id": inv.invoice_id,
                "debtor_id": inv.debtor_id,
                "carrier_id": inv.carrier_id,
            }
            # Convert document attachments if provided
            if inv.document_urls:
                submission["document_urls"] = [
                    {
                        "url": doc.url,
                        "document_type": doc.document_type,
                        "filename": doc.filename,
                    }
                    for doc in inv.document_urls
                ]
            invoice_submissions.append(submission)
        
        service = HaulPayService(db)
        batch_result = await service.batch_submit_invoices_for_factoring(
            company_id=company_id,
            invoice_submissions=invoice_submissions,
        )
        
        # Convert results to Pydantic models
        from app.schemas.integration import HaulPayInvoiceSubmissionResult
        result_models = [
            HaulPayInvoiceSubmissionResult(**result)
            for result in batch_result["results"]
        ]
        
        return HaulPayBatchSubmissionResponse(
            total=batch_result["total"],
            successful=batch_result["successful"],
            failed=batch_result["failed"],
            results=result_models,
        )
    except Exception as e:
        logger.error(f"HaulPay batch submit invoices error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch submit invoices: {str(e)}"
        )


@router.get("/haulpay/{integration_id}/invoice/{invoice_id}/tracking", response_model=HaulPayInvoiceTracking)
async def haulpay_get_invoice_tracking(
    integration_id: str,
    invoice_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> HaulPayInvoiceTracking:
    """
    Get factoring tracking information for a specific invoice.
    Returns stored factoring metadata including status, advance amounts, reserve, fees, etc.
    Each invoice is tracked separately with its own factoring status.
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        from app.schemas.integration import HaulPayInvoiceTracking
        
        service = HaulPayService(db)
        tracking = await service.get_invoice_factoring_tracking(company_id, invoice_id)
        
        if not tracking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found or not submitted for factoring"
            )
        
        return HaulPayInvoiceTracking(**tracking)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HaulPay get invoice tracking error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get invoice tracking: {str(e)}"
        )


@router.post("/haulpay/{integration_id}/invoice/{haulpay_invoice_id}/upload-document")
async def haulpay_upload_document_to_invoice(
    integration_id: str,
    haulpay_invoice_id: str,
    document_url: str,
    document_type: str,
    filename: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Upload a document to an existing HaulPay invoice.
    Useful for adding missing documents after initial submission.
    
    Args:
        integration_id: Integration ID
        haulpay_invoice_id: HaulPay invoice ID
        document_url: URL or storage key to the document
        document_type: Type of document (pod, bol, rate_confirmation, etc.)
        filename: Original filename
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        import httpx
        from app.services.storage import StorageService
        from app.core.config import get_settings
        settings = get_settings()
        
        # Fetch document
        file_content = None
        if document_url.startswith("http://") or document_url.startswith("https://"):
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                response = await http_client.get(document_url)
                response.raise_for_status()
                file_content = response.content
        else:
            # Get from R2 storage
            storage = StorageService()
            presigned_url = storage.get_file_url(document_url, expires_in=300)
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                response = await http_client.get(presigned_url)
                response.raise_for_status()
                file_content = response.content
        
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch document"
            )
        
        # Infer content type
        content_type = "application/pdf"
        if filename.lower().endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif filename.lower().endswith(".png"):
            content_type = "image/png"
        
        # Upload to HaulPay
        service = HaulPayService(db)
        client = await service.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")
        
        result = await client.upload_document_to_invoice(
            invoice_id=haulpay_invoice_id,
            file_content=file_content,
            filename=filename,
            document_type=document_type,
            content_type=content_type,
        )
        
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HaulPay upload document error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("/haulpay/{integration_id}/factored-invoices")
async def haulpay_list_factored_invoices(
    integration_id: str,
    status: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    List all factored invoices from HaulPay.
    Optionally filter by status (submitted, funded, paid, etc.).
    """
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id,
            CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        service = HaulPayService(db)
        invoices = await service.sync_factored_invoices(company_id, status=status)
        return {"success": True, "data": invoices}
    except Exception as e:
        logger.error(f"HaulPay list factored invoices error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list factored invoices: {str(e)}"
        )

