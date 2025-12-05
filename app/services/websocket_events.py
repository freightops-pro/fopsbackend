"""
WebSocket event handler that subscribes to application events
and broadcasts them to connected clients.

This module bridges the event dispatcher with the WebSocket layer,
providing a clean separation between business logic and real-time updates.
"""
import logging
from app.services.event_dispatcher import (
    Event,
    EventType,
    subscribe,
    subscribe_all,
)
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)


async def handle_driver_event(event: Event) -> None:
    """Handle driver-related events."""
    data = event.data
    company_id = event.company_id or data.get("company_id")
    driver_id = data.get("driver_id")

    if not company_id:
        logger.warning(f"Driver event missing company_id: {event.type}")
        return

    message = {
        "type": "driver_update",
        "data": {
            "driver_id": driver_id,
            "event_type": event.type.value.split(".")[-1],  # e.g., "updated" from "driver.updated"
            "timestamp": event.timestamp,
            **data,
        }
    }

    await manager.send_company_message(message, company_id)
    logger.debug(f"Broadcast driver event: {event.type.value}")


async def handle_load_event(event: Event) -> None:
    """Handle load-related events."""
    data = event.data
    company_id = event.company_id or data.get("company_id")
    load_id = data.get("load_id")

    if not company_id:
        logger.warning(f"Load event missing company_id: {event.type}")
        return

    message = {
        "type": "load_update",
        "data": {
            "load_id": load_id,
            "event_type": event.type.value.split(".")[-1],
            "timestamp": event.timestamp,
            **data,
        }
    }

    await manager.send_company_message(message, company_id)
    logger.debug(f"Broadcast load event: {event.type.value}")


async def handle_load_assigned(event: Event) -> None:
    """Handle load assignment - notify the driver directly."""
    data = event.data
    driver_id = event.target_driver_id or data.get("driver_id")
    company_id = event.company_id or data.get("company_id")

    # Send to specific driver
    if driver_id:
        from app.routers.websocket import send_to_driver
        await send_to_driver(driver_id, "load_assigned", {
            "load_id": data.get("load_id"),
            "reference_number": data.get("reference_number"),
            "origin": data.get("origin"),
            "destination": data.get("destination"),
            "pickup_date": data.get("pickup_date"),
            "timestamp": event.timestamp,
        })

    # Also broadcast to company
    if company_id:
        await handle_load_event(event)


async def handle_load_unassigned(event: Event) -> None:
    """Handle load unassignment - notify the driver directly."""
    data = event.data
    driver_id = event.target_driver_id or data.get("driver_id")
    company_id = event.company_id or data.get("company_id")

    # Send to specific driver
    if driver_id:
        from app.routers.websocket import send_to_driver
        await send_to_driver(driver_id, "load_unassigned", {
            "load_id": data.get("load_id"),
            "reference_number": data.get("reference_number"),
            "reason": data.get("reason"),
            "timestamp": event.timestamp,
        })

    # Also broadcast to company
    if company_id:
        await handle_load_event(event)


async def handle_location_event(event: Event) -> None:
    """Handle location update events."""
    data = event.data
    company_id = event.company_id or data.get("company_id")
    driver_id = data.get("driver_id")

    if not company_id:
        return

    message = {
        "type": "location_update",
        "data": {
            "driver_id": driver_id,
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "speed": data.get("speed"),
            "heading": data.get("heading"),
            "accuracy": data.get("accuracy"),
            "load_id": data.get("load_id"),
            "timestamp": event.timestamp,
        }
    }

    await manager.send_company_message(message, company_id)


async def handle_document_event(event: Event) -> None:
    """Handle document-related events."""
    data = event.data
    company_id = event.company_id or data.get("company_id")
    driver_id = event.target_driver_id or data.get("driver_id")
    event_subtype = event.type.value.split(".")[-1]  # uploaded, approved, rejected

    message = {
        "type": f"document_{event_subtype}",
        "data": {
            "document_id": data.get("document_id"),
            "document_type": data.get("document_type"),
            "load_id": data.get("load_id"),
            "driver_id": driver_id,
            "timestamp": event.timestamp,
            **data,
        }
    }

    # Send to specific driver for approval/rejection
    if driver_id and event_subtype in ("approved", "rejected"):
        from app.routers.websocket import send_to_driver
        await send_to_driver(driver_id, f"document_{event_subtype}", data)

    # Broadcast to company
    if company_id:
        await manager.send_company_message(message, company_id)


async def handle_equipment_event(event: Event) -> None:
    """Handle equipment-related events."""
    data = event.data
    company_id = event.company_id or data.get("company_id")
    driver_id = event.target_driver_id or data.get("driver_id")
    event_subtype = event.type.value.split(".")[-1]

    message = {
        "type": "equipment_update",
        "data": {
            "equipment_id": data.get("equipment_id"),
            "event_type": event_subtype,
            "timestamp": event.timestamp,
            **data,
        }
    }

    # Notify driver directly for assignment changes
    if driver_id and event_subtype in ("assigned", "unassigned"):
        from app.routers.websocket import send_to_driver
        await send_to_driver(driver_id, f"truck_{event_subtype}", data)

    # Broadcast to company
    if company_id:
        await manager.send_company_message(message, company_id)


async def handle_stop_event(event: Event) -> None:
    """Handle stop events (arrival/departure)."""
    data = event.data
    company_id = event.company_id or data.get("company_id")
    event_subtype = event.type.value.split(".")[-1]  # driver_arrived, driver_departed

    if not company_id:
        return

    message = {
        "type": "load_update",
        "data": {
            "load_id": data.get("load_id"),
            "event_type": event_subtype,
            "stop_id": data.get("stop_id"),
            "driver_id": data.get("driver_id"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "timestamp": event.timestamp,
        }
    }

    await manager.send_company_message(message, company_id)


def register_websocket_handlers() -> None:
    """Register all WebSocket event handlers with the dispatcher."""
    # Driver events
    subscribe(EventType.DRIVER_CREATED, handle_driver_event)
    subscribe(EventType.DRIVER_UPDATED, handle_driver_event)
    subscribe(EventType.DRIVER_DELETED, handle_driver_event)
    subscribe(EventType.DRIVER_STATUS_CHANGED, handle_driver_event)
    subscribe(EventType.DRIVER_LOCATION_UPDATED, handle_location_event)

    # Load events
    subscribe(EventType.LOAD_CREATED, handle_load_event)
    subscribe(EventType.LOAD_UPDATED, handle_load_event)
    subscribe(EventType.LOAD_DELETED, handle_load_event)
    subscribe(EventType.LOAD_STATUS_CHANGED, handle_load_event)
    subscribe(EventType.LOAD_ASSIGNED, handle_load_assigned)
    subscribe(EventType.LOAD_UNASSIGNED, handle_load_unassigned)

    # Stop events
    subscribe(EventType.DRIVER_ARRIVED, handle_stop_event)
    subscribe(EventType.DRIVER_DEPARTED, handle_stop_event)

    # Document events
    subscribe(EventType.DOCUMENT_UPLOADED, handle_document_event)
    subscribe(EventType.DOCUMENT_APPROVED, handle_document_event)
    subscribe(EventType.DOCUMENT_REJECTED, handle_document_event)

    # Equipment events
    subscribe(EventType.EQUIPMENT_UPDATED, handle_equipment_event)
    subscribe(EventType.EQUIPMENT_ASSIGNED, handle_equipment_event)
    subscribe(EventType.EQUIPMENT_UNASSIGNED, handle_equipment_event)
    subscribe(EventType.EQUIPMENT_INSPECTION, handle_equipment_event)

    # Message events
    subscribe(EventType.MESSAGE_SENT, handle_message_event)

    logger.info("WebSocket event handlers registered")


async def handle_message_event(event: Event) -> None:
    """Handle chat message events - send to specific driver."""
    data = event.data
    driver_id = event.target_driver_id or data.get("driver_id")
    company_id = event.company_id or data.get("company_id")

    message = {
        "type": "chat_message",
        "data": {
            "id": data.get("id"),
            "channel_id": data.get("channel_id"),
            "author_id": data.get("author_id"),
            "author_name": data.get("author_name"),
            "body": data.get("body"),
            "created_at": data.get("created_at"),
            "is_from_driver": data.get("is_from_driver", False),
            "timestamp": event.timestamp,
        }
    }

    # Send to specific driver if targeted
    if driver_id:
        from app.routers.websocket import send_to_driver
        await send_to_driver(driver_id, "chat_message", message["data"])
        logger.debug(f"Sent chat message to driver {driver_id}")

    # Broadcast to company for dispatch dashboard
    if company_id:
        await manager.send_company_message(message, company_id)
        logger.debug(f"Broadcast chat message to company {company_id}")
