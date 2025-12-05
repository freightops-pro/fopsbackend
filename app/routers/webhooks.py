"""Router for handling webhook events from third-party integrations."""

import hmac
import hashlib
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.integration import CompanyIntegration, Integration

logger = logging.getLogger(__name__)

router = APIRouter()


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Get current user's company ID."""
    return current_user.company_id


@router.post("/motive/company/{integration_id}")
async def handle_motive_webhook(
    integration_id: str,
    request: Request,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Handle webhook events from Motive (authenticated endpoint for internal use)."""
    # Verify integration exists and belongs to company
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Verify webhook signature (if Motive provides one)
    # For now, we'll just log the event
    try:
        payload = await request.json()
        event_type = payload.get("event_type") or payload.get("type")
        event_data = payload.get("data") or payload

        logger.info(f"Received Motive webhook: {event_type} for integration {integration_id}")

        # Handle different event types
        if event_type in ["vehicle.location", "location.updated"]:
            await handle_vehicle_location_event(db, integration, event_data)
        elif event_type in ["hos.violation", "violation.created"]:
            await handle_hos_violation_event(db, integration, event_data)
        elif event_type in ["hos.status", "hos.updated"]:
            await handle_hos_status_event(db, integration, event_data)
        elif event_type in ["geofence.entry", "geofence.exit"]:
            await handle_geofence_event(db, integration, event_data)
        elif event_type in ["fault_code.created", "fault_code.updated"]:
            await handle_fault_code_event(db, integration, event_data)
        else:
            logger.warning(f"Unhandled Motive webhook event type: {event_type}")

        return {"success": True, "message": "Webhook processed"}
    except Exception as e:
        logger.error(f"Error processing Motive webhook: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process webhook: {str(e)}")


@router.post("/motive")
async def handle_motive_webhook_public(
    request: Request,
    x_kt_webhook_signature: Optional[str] = Header(None, alias="X-KT-Webhook-Signature"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Public webhook endpoint for Motive events.
    
    This endpoint is called by Motive's servers and does not require authentication.
    Webhook signature validation uses HMAC-SHA1 as per Motive's documentation.
    
    According to Motive docs:
    - Signature header: X-KT-Webhook-Signature
    - Algorithm: HMAC-SHA1
    - Must respond within 3 seconds with 200/201 status
    - Test request payload: ["vehicle_location_updated"]
    """
    try:
        payload = await request.body()
        payload_json = await request.json()
        
        # Handle test request (when webhook is enabled/updated)
        # Motive sends ["vehicle_location_updated"] as test payload
        if isinstance(payload_json, list) and len(payload_json) == 1 and payload_json[0] == "vehicle_location_updated":
            logger.info("Received Motive webhook test request")
            # Return 200 immediately for test requests
            return {"success": True, "message": "Webhook test successful"}
        
        # Validate webhook signature if Motive provides one
        # Motive uses HMAC-SHA1 (not SHA256)
        if x_kt_webhook_signature:
            # Find integration to get webhook secret
            result = await db.execute(
                select(CompanyIntegration)
                .join(Integration)
                .where(
                    Integration.integration_key == "motive",
                    CompanyIntegration.status == "active"
                )
            )
            integrations = list(result.scalars().all())
            
            # Find integration with webhook secret
            webhook_secret = None
            integration = None
            for intg in integrations:
                if intg.config and intg.config.get("webhook_secret"):
                    webhook_secret = intg.config.get("webhook_secret")
                    integration = intg
                    break
            
            if webhook_secret:
                # Validate signature (Motive uses HMAC-SHA1 per documentation)
                expected_signature = hmac.new(
                    webhook_secret.encode(), payload, hashlib.sha1
                ).hexdigest()
                if not hmac.compare_digest(x_kt_webhook_signature, expected_signature):
                    logger.warning("Invalid webhook signature")
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature")
        
        # Extract action from payload (Motive webhooks use "action" field)
        action = payload_json.get("action")
        event_type = payload_json.get("event_type") or payload_json.get("type") or action
        event_data = payload_json
        
        logger.info(f"Received Motive webhook: action={action}, event_type={event_type}")
        
        # Find integration - use the one we found during signature validation, or find one now
        if not integration:
            result = await db.execute(
                select(CompanyIntegration)
                .join(Integration)
                .where(
                    Integration.integration_key == "motive",
                    CompanyIntegration.status == "active"
                )
                .limit(1)
            )
            integration = result.scalar_one_or_none()
        
        if integration:
            # Route to appropriate handler based on Motive action names
            if action == "vehicle_location_updated" or action == "vehicle_location_received":
                await handle_vehicle_location_event(db, integration, event_data)
            elif action == "hos_violation_upserted":
                await handle_hos_violation_event(db, integration, event_data)
            elif action == "vehicle_geofence_event" or action == "asset_geofence_event":
                await handle_geofence_event(db, integration, event_data)
            elif action == "fault_code_opened" or action == "fault_code_closed":
                await handle_fault_code_event(db, integration, event_data)
            elif action == "vehicle_upserted":
                # Vehicle created/updated - could trigger equipment sync
                logger.info(f"Vehicle upserted: {event_data.get('id')}")
            elif action == "user_upserted":
                # User created/updated - could trigger driver sync
                logger.info(f"User upserted: {event_data.get('id')}")
            elif action == "engine_toggle_event":
                # Engine on/off event
                logger.info(f"Engine toggle: {event_data.get('trigger')} for vehicle {event_data.get('vehicle_id')}")
            elif action == "driver_performance_event_created" or action == "driver_performance_event_updated":
                # Driver performance event
                logger.info(f"Driver performance event: {event_data.get('type')}")
            elif action == "speeding_event_created" or action == "speeding_event_updated":
                # Speeding event
                logger.info(f"Speeding event for driver {event_data.get('driver_id')}")
            else:
                logger.info(f"Received unhandled Motive webhook action: {action}")
        
        return {"success": True, "message": "Webhook processed"}
    except Exception as e:
        logger.error(f"Error processing Motive webhook: {e}", exc_info=True)
        # Return 200 to prevent Motive from retrying invalid requests
        return {"success": False, "error": str(e)}


@router.post("/motive/company/{integration_id}")
async def handle_motive_webhook(
    integration_id: str,
    request: Request,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Handle webhook events from Motive (authenticated endpoint for internal use)."""
    # Verify integration exists and belongs to company
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.id == integration_id, CompanyIntegration.company_id == company_id
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Verify webhook signature (if Motive provides one)
    # For now, we'll just log the event
    try:
        payload = await request.json()
        event_type = payload.get("event_type") or payload.get("type")
        event_data = payload.get("data") or payload

        logger.info(f"Received Motive webhook: {event_type} for integration {integration_id}")

        # Handle different event types
        if event_type in ["vehicle.location", "location.updated"]:
            await handle_vehicle_location_event(db, integration, event_data)
        elif event_type in ["hos.violation", "violation.created"]:
            await handle_hos_violation_event(db, integration, event_data)
        elif event_type in ["hos.status", "hos.updated"]:
            await handle_hos_status_event(db, integration, event_data)
        elif event_type in ["geofence.entry", "geofence.exit"]:
            await handle_geofence_event(db, integration, event_data)
        elif event_type in ["fault_code.created", "fault_code.updated"]:
            await handle_fault_code_event(db, integration, event_data)
        else:
            logger.warning(f"Unhandled Motive webhook event type: {event_type}")

        return {"success": True, "message": "Webhook processed"}
    except Exception as e:
        logger.error(f"Error processing Motive webhook: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process webhook: {str(e)}")


async def handle_vehicle_location_event(
    db: AsyncSession, integration: CompanyIntegration, event_data: Dict[str, Any]
):
    """Handle vehicle location update event."""
    vehicle_id = event_data.get("vehicle_id")
    if vehicle_id:
        # Update vehicle location in equipment table
        # This would trigger real-time updates in the dispatch board
        logger.info(f"Vehicle location update: {vehicle_id}")
        
        # Optionally notify driver via chat if driver_id is available
        driver_id = event_data.get("driver_id")
        if driver_id:
            from app.services.webhook_chat import WebhookChatService
            chat_service = WebhookChatService(db)
            try:
                await chat_service.notify_driver_webhook_event(
                    company_id=integration.company_id,
                    driver_id=driver_id,
                    event_type="vehicle_location",
                    event_data=event_data,
                )
            except Exception as e:
                logger.error(f"Failed to send chat notification for location update: {e}")


async def handle_hos_violation_event(
    db: AsyncSession, integration: CompanyIntegration, event_data: Dict[str, Any]
):
    """Handle HOS violation event."""
    driver_id = event_data.get("driver_id") or event_data.get("user_id")
    if driver_id:
        # Create or update violation record
        # This would trigger alerts in the driver compliance workspace
        logger.info(f"HOS violation event: {driver_id}")
        
        # Notify driver via chat
        from app.services.webhook_chat import WebhookChatService
        chat_service = WebhookChatService(db)
        try:
            await chat_service.notify_driver_webhook_event(
                company_id=integration.company_id,
                driver_id=driver_id,
                event_type="hos_violation",
                event_data=event_data,
            )
        except Exception as e:
            logger.error(f"Failed to send chat notification for HOS violation: {e}")


async def handle_hos_status_event(
    db: AsyncSession, integration: CompanyIntegration, event_data: Dict[str, Any]
):
    """Handle HOS status update event."""
    driver_id = event_data.get("driver_id") or event_data.get("user_id")
    if driver_id:
        # Update driver HOS status
        # This would update the dispatch board with availability
        logger.info(f"HOS status update: {driver_id}")
        
        # Optionally notify driver via chat (only for significant status changes)
        status = event_data.get("status")
        if status in ["off_duty", "sleeper_berth", "driving", "on_duty"]:
            from app.services.webhook_chat import WebhookChatService
            chat_service = WebhookChatService(db)
            try:
                await chat_service.notify_driver_webhook_event(
                    company_id=integration.company_id,
                    driver_id=driver_id,
                    event_type="hos_status",
                    event_data=event_data,
                )
            except Exception as e:
                logger.error(f"Failed to send chat notification for HOS status: {e}")


async def handle_geofence_event(
    db: AsyncSession, integration: CompanyIntegration, event_data: Dict[str, Any]
):
    """Handle geofence entry/exit event."""
    vehicle_id = event_data.get("vehicle_id")
    geofence_id = event_data.get("geofence_id")
    event_type = event_data.get("event_type") or event_data.get("action", "").replace("vehicle_geofence_event", "geofence_entry")
    if vehicle_id and geofence_id:
        # Update pickup workflow if vehicle enters pickup geofence
        logger.info(f"Geofence event: {event_type} for vehicle {vehicle_id} at geofence {geofence_id}")
        
        # Notify driver via chat
        driver_id = event_data.get("driver_id")
        if driver_id:
            from app.services.webhook_chat import WebhookChatService
            chat_service = WebhookChatService(db)
            try:
                await chat_service.notify_driver_webhook_event(
                    company_id=integration.company_id,
                    driver_id=driver_id,
                    event_type="geofence_entry" if "entry" in str(event_type).lower() else "geofence_exit",
                    event_data={**event_data, "geofence_name": geofence_id},
                )
            except Exception as e:
                logger.error(f"Failed to send chat notification for geofence event: {e}")


async def handle_fault_code_event(
    db: AsyncSession, integration: CompanyIntegration, event_data: Dict[str, Any]
):
    """Handle fault code event."""
    vehicle_id = event_data.get("vehicle_id")
    fault_code = event_data.get("fault_code")
    if vehicle_id and fault_code:
        # Create maintenance alert
        # This would trigger alerts in the equipment management page
        logger.info(f"Fault code event: {fault_code} for vehicle {vehicle_id}")
        
        # Notify driver via chat
        driver_id = event_data.get("driver_id")
        if driver_id:
            from app.services.webhook_chat import WebhookChatService
            chat_service = WebhookChatService(db)
            try:
                await chat_service.notify_driver_webhook_event(
                    company_id=integration.company_id,
                    driver_id=driver_id,
                    event_type="fault_code",
                    event_data=event_data,
                )
            except Exception as e:
                logger.error(f"Failed to send chat notification for fault code: {e}")


@router.post("/chat/notify-driver")
async def notify_driver_chat(
    request: Request,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Webhook endpoint to send chat notifications to drivers.
    Used by internal systems (dispatch, automation) to notify drivers via chat.
    
    Expected payload:
    {
        "driver_id": "driver-uuid",
        "message": "Custom message text",
        "event_type": "load_assignment" | "pickup_reminder" | "custom",
        "event_data": {...}
    }
    """
    try:
        payload = await request.json()
        driver_id = payload.get("driver_id")
        message = payload.get("message")
        event_type = payload.get("event_type", "custom")
        event_data = payload.get("event_data", {})

        if not driver_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="driver_id is required")

        from app.services.webhook_chat import WebhookChatService
        chat_service = WebhookChatService(db)

        if message:
            # Use custom message
            channel = await chat_service.get_or_create_driver_channel(company_id, driver_id)
            await chat_service.create_system_message(channel.id, message)
        else:
            # Use event-based message formatting
            await chat_service.notify_driver_webhook_event(
                company_id=company_id,
                driver_id=driver_id,
                event_type=event_type,
                event_data=event_data,
            )

        return {"success": True, "message": "Chat notification sent"}
    except Exception as e:
        logger.error(f"Error sending chat notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send chat notification: {str(e)}"
        )


@router.post("/chat/notify-load-assignment")
async def notify_load_assignment_chat(
    request: Request,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Webhook endpoint to notify drivers about load assignments via chat.
    
    Expected payload:
    {
        "driver_id": "driver-uuid",
        "load_id": "load-uuid",
        "load_details": {
            "pickup_location": {"address": "..."},
            "delivery_location": {"address": "..."}
        }
    }
    """
    try:
        payload = await request.json()
        driver_id = payload.get("driver_id")
        load_id = payload.get("load_id")
        load_details = payload.get("load_details", {})

        if not driver_id or not load_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="driver_id and load_id are required"
            )

        from app.services.webhook_chat import WebhookChatService
        chat_service = WebhookChatService(db)

        await chat_service.notify_load_assignment(
            company_id=company_id,
            driver_id=driver_id,
            load_id=load_id,
            load_details=load_details,
        )

        return {"success": True, "message": "Load assignment notification sent"}
    except Exception as e:
        logger.error(f"Error sending load assignment notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send load assignment notification: {str(e)}"
        )


@router.post("/chat/notify-pickup-reminder")
async def notify_pickup_reminder_chat(
    request: Request,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Webhook endpoint to send pickup reminders to drivers via chat.
    
    Expected payload:
    {
        "driver_id": "driver-uuid",
        "load_id": "load-uuid",
        "pickup_time": "2024-01-15 10:00:00",
        "location": "123 Main St, City, State"
    }
    """
    try:
        payload = await request.json()
        driver_id = payload.get("driver_id")
        load_id = payload.get("load_id")
        pickup_time = payload.get("pickup_time")
        location = payload.get("location")

        if not driver_id or not load_id or not pickup_time or not location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="driver_id, load_id, pickup_time, and location are required"
            )

        from app.services.webhook_chat import WebhookChatService
        chat_service = WebhookChatService(db)

        await chat_service.notify_pickup_reminder(
            company_id=company_id,
            driver_id=driver_id,
            load_id=load_id,
            pickup_time=pickup_time,
            location=location,
        )

        return {"success": True, "message": "Pickup reminder sent"}
    except Exception as e:
        logger.error(f"Error sending pickup reminder: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send pickup reminder: {str(e)}"
        )

