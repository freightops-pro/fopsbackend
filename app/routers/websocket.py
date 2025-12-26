"""WebSocket router for real-time bi-directional updates."""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.core.db import get_db
from app.services.websocket_manager import manager
from app.models.driver import Driver

router = APIRouter()
logger = logging.getLogger(__name__)

# Store driver-to-websocket mappings for targeted messages
driver_connections: dict[str, str] = {}  # driver_id -> user_id


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for real-time bi-directional updates.

    Clients connect with token as query parameter:
    ws://host/api/ws?token=<access_token>

    Message Types (Client -> Server):
    - ping: Keep-alive
    - register_driver: Register driver for targeted notifications
    - location_update: Driver location update
    - load_status_update: Load status change
    - driver_arrival: Driver arrived at stop
    - driver_departure: Driver departed from stop
    - document_upload_started: Document upload in progress
    - document_upload_completed: Document upload finished
    - request_equipment_sync: Request equipment data
    - request_driver_sync: Request driver data
    - driver_status_update: Driver availability status
    - truck_inspection: Truck inspection report
    - subscribe/unsubscribe: Topic subscriptions

    Message Types (Server -> Client):
    - system_message: System notifications
    - driver_update: Driver profile changes
    - load_update: Load status changes
    - load_assigned/load_unassigned: Load assignment changes
    - location_update: Driver location (for dispatch)
    - document_uploaded/approved/rejected: Document status
    - equipment_update: Equipment changes
    - truck_assigned/unassigned: Truck assignment changes
    - notification: General notifications
    """
    user = None
    driver_id = None
    try:
        # Accept the WebSocket connection first
        await websocket.accept()

        # Authenticate user from WebSocket headers or query params
        user = await deps.get_current_user_websocket(websocket, db)

        if not user:
            # Authentication failed - send error message and close
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Authentication failed", "code": "auth_failed"}
            })
            await websocket.close(code=1008, reason="Authentication failed")
            return

        # Register with the WebSocket manager
        await manager.connect(websocket, user)

        # Check if user is a driver
        driver_result = await db.execute(
            select(Driver).where(Driver.user_id == str(user.id))
        )
        driver = driver_result.scalar_one_or_none()
        if driver:
            driver_id = str(driver.id)
            driver_connections[driver_id] = str(user.id)

        # Send welcome message
        await websocket.send_json({
            "type": "system_message",
            "data": {
                "message": "Connected to FreightOps real-time updates",
                "user_id": str(user.id),
                "company_id": str(user.company_id) if user.company_id else None,
                "driver_id": driver_id,
            }
        })

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # Handle different message types
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "register_driver":
                # Register driver for targeted notifications
                reg_data = data.get("data", {})
                driver_id = reg_data.get("driver_id")
                if driver_id:
                    driver_connections[driver_id] = str(user.id)
                    await websocket.send_json({
                        "type": "registration_ack",
                        "data": {"driver_id": driver_id, "status": "registered"}
                    })

            elif msg_type == "location_update":
                # Handle location update from driver
                await handle_location_update(data.get("data", {}), user, db)
                await websocket.send_json({"type": "location_ack"})

            elif msg_type == "load_status_update":
                # Handle load status change
                await handle_load_status_update(data.get("data", {}), user, db)

            elif msg_type == "driver_arrival":
                # Handle driver arrival at stop
                await handle_driver_arrival(data.get("data", {}), user, db)

            elif msg_type == "driver_departure":
                # Handle driver departure from stop
                await handle_driver_departure(data.get("data", {}), user, db)

            elif msg_type == "document_upload_started":
                # Broadcast document upload started
                doc_data = data.get("data", {})
                await broadcast_document_event(
                    doc_data.get("load_id"),
                    str(user.company_id),
                    "document_upload_started",
                    doc_data
                )

            elif msg_type == "document_upload_completed":
                # Broadcast document upload completed
                doc_data = data.get("data", {})
                await broadcast_document_event(
                    doc_data.get("load_id"),
                    str(user.company_id),
                    "document_uploaded",
                    doc_data
                )

            elif msg_type == "request_equipment_sync":
                # Send equipment data to driver
                await send_equipment_sync(websocket, data.get("data", {}), user, db)

            elif msg_type == "request_driver_sync":
                # Send driver data
                await send_driver_sync(websocket, data.get("data", {}), user, db)

            elif msg_type == "driver_status_update":
                # Handle driver status change
                await handle_driver_status_update(data.get("data", {}), user, db)

            elif msg_type == "truck_inspection":
                # Handle truck inspection report
                await handle_truck_inspection(data.get("data", {}), user, db)

            elif msg_type == "subscribe":
                topics = data.get("topics", [])
                logger.debug(f"Subscription request from user {user.id}: {topics}")
                await websocket.send_json({
                    "type": "subscription_ack",
                    "data": {"topics": topics, "status": "subscribed"}
                })

            elif msg_type == "unsubscribe":
                topics = data.get("topics", [])
                logger.debug(f"Unsubscription request from user {user.id}: {topics}")
                await websocket.send_json({
                    "type": "subscription_ack",
                    "data": {"topics": topics, "status": "unsubscribed"}
                })

            elif msg_type == "chat_message":
                # Handle chat message from driver
                await handle_chat_message(data.get("data", {}), user, driver_id, db)

            elif msg_type == "get_messages":
                # Get message history for driver
                await send_message_history(websocket, data.get("data", {}), user, db)

            elif msg_type == "mark_read":
                # Mark messages as read
                await handle_mark_read(data.get("data", {}), user, db)

            else:
                logger.warning(f"Unknown message type from user {user.id}: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally - User: {user.email if user else 'Unknown'}")
        if user:
            await manager.disconnect(websocket, user)
        if driver_id and driver_id in driver_connections:
            del driver_connections[driver_id]

    except Exception as e:
        logger.error(f"WebSocket error - User: {user.email if user else 'Unknown'}: {e}", exc_info=True)
        if user:
            await manager.disconnect(websocket, user)
        if driver_id and driver_id in driver_connections:
            del driver_connections[driver_id]
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


# ==================== MESSAGE HANDLERS ====================

async def handle_location_update(data: dict, user, db: AsyncSession) -> None:
    """Process and broadcast driver location update."""
    driver_id = data.get("driver_id")
    company_id = data.get("company_id") or str(user.company_id)

    if not driver_id:
        logger.warning(f"Location update missing driver_id from user {user.id}")
        return

    # Store location in database (optional - can be added later)
    # For now, just broadcast to company

    await broadcast_location_update(driver_id, company_id, {
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "speed": data.get("speed"),
        "heading": data.get("heading"),
        "accuracy": data.get("accuracy"),
        "load_id": data.get("load_id"),
        "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
    })


async def handle_load_status_update(data: dict, user, db: AsyncSession) -> None:
    """Process load status update from driver."""
    load_id = data.get("load_id")
    status = data.get("status")
    company_id = str(user.company_id)

    if not load_id or not status:
        logger.warning(f"Load status update missing required fields from user {user.id}")
        return

    # Broadcast status change to company
    await broadcast_load_update(load_id, company_id, "status_changed", {
        "status": status,
        "driver_id": data.get("driver_id"),
        "stop_id": data.get("stop_id"),
        "metadata": data.get("metadata"),
        "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
    })


async def handle_driver_arrival(data: dict, user, db: AsyncSession) -> None:
    """Process driver arrival at stop."""
    load_id = data.get("load_id")
    stop_id = data.get("stop_id")
    company_id = str(user.company_id)

    if not load_id or not stop_id:
        return

    await broadcast_load_update(load_id, company_id, "driver_arrived", {
        "driver_id": data.get("driver_id"),
        "stop_id": stop_id,
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
    })


async def handle_driver_departure(data: dict, user, db: AsyncSession) -> None:
    """Process driver departure from stop."""
    load_id = data.get("load_id")
    stop_id = data.get("stop_id")
    company_id = str(user.company_id)

    if not load_id or not stop_id:
        return

    await broadcast_load_update(load_id, company_id, "driver_departed", {
        "driver_id": data.get("driver_id"),
        "stop_id": stop_id,
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
    })


async def handle_driver_status_update(data: dict, user, db: AsyncSession) -> None:
    """Process driver status change (available, on_duty, etc.)."""
    driver_id = data.get("driver_id")
    status = data.get("status")
    company_id = str(user.company_id)

    if not driver_id or not status:
        return

    await broadcast_driver_update(driver_id, company_id, "status_changed", {
        "status": status,
        "metadata": data.get("metadata"),
        "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
    })


async def handle_truck_inspection(data: dict, user, db: AsyncSession) -> None:
    """Process truck inspection report."""
    equipment_id = data.get("equipment_id")
    company_id = str(user.company_id)

    if not equipment_id:
        return

    await broadcast_equipment_update(equipment_id, company_id, "inspection_completed", {
        "driver_id": data.get("driver_id"),
        "inspection_type": data.get("inspection_type"),
        "passed": data.get("passed"),
        "defects": data.get("defects"),
        "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
    })


async def send_equipment_sync(websocket: WebSocket, data: dict, user, db: AsyncSession) -> None:
    """Send equipment data to driver."""
    driver_id = data.get("driver_id")

    # Query equipment assigned to driver
    from app.models.equipment import Equipment
    from app.models.driver import Driver

    driver_result = await db.execute(
        select(Driver).where(Driver.id == driver_id)
    )
    driver = driver_result.scalar_one_or_none()

    equipment_data = None
    if driver and driver.assigned_equipment_id:
        equip_result = await db.execute(
            select(Equipment).where(Equipment.id == driver.assigned_equipment_id)
        )
        equipment = equip_result.scalar_one_or_none()
        if equipment:
            equipment_data = {
                "id": str(equipment.id),
                "unit_number": equipment.unit_number,
                "equipment_type": equipment.equipment_type,
                "make": equipment.make,
                "model": equipment.model,
                "year": equipment.year,
                "vin": equipment.vin,
                "license_plate": equipment.license_plate,
                "status": equipment.status,
            }

    await websocket.send_json({
        "type": "equipment_update",
        "data": {
            "event_type": "sync",
            "equipment": equipment_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
    })


async def send_driver_sync(websocket: WebSocket, data: dict, user, db: AsyncSession) -> None:
    """Send driver profile data."""
    driver_id = data.get("driver_id")

    driver_result = await db.execute(
        select(Driver).where(Driver.id == driver_id)
    )
    driver = driver_result.scalar_one_or_none()

    driver_data = None
    if driver:
        driver_data = {
            "id": str(driver.id),
            "first_name": driver.first_name,
            "last_name": driver.last_name,
            "email": driver.email,
            "phone": driver.phone,
            "cdl_number": driver.cdl_number,
            "cdl_expiration": str(driver.cdl_expiration) if driver.cdl_expiration else None,
            "medical_card_expiration": str(driver.medical_card_expiration) if driver.medical_card_expiration else None,
            "assigned_equipment_id": str(driver.assigned_equipment_id) if driver.assigned_equipment_id else None,
        }

    await websocket.send_json({
        "type": "driver_update",
        "data": {
            "event_type": "sync",
            "driver": driver_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
    })


# ==================== BROADCAST HELPERS ====================

async def broadcast_driver_update(driver_id: str, company_id: str, event_type: str, data: dict) -> None:
    """Broadcast driver-related updates to all users in the company."""
    message = {
        "type": "driver_update",
        "data": {
            "driver_id": driver_id,
            "event_type": event_type,
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
            **data
        }
    }
    await manager.send_company_message(message, company_id)


async def broadcast_load_update(load_id: str, company_id: str, event_type: str, data: dict) -> None:
    """Broadcast load-related updates to all users in the company."""
    message = {
        "type": "load_update",
        "data": {
            "load_id": load_id,
            "event_type": event_type,
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
            **data
        }
    }
    await manager.send_company_message(message, company_id)


async def broadcast_location_update(driver_id: str, company_id: str, location_data: dict) -> None:
    """Broadcast driver location updates to all users in the company."""
    message = {
        "type": "location_update",
        "data": {
            "driver_id": driver_id,
            **location_data
        }
    }
    await manager.send_company_message(message, company_id)


async def broadcast_document_event(load_id: str, company_id: str, event_type: str, data: dict) -> None:
    """Broadcast document-related events."""
    message = {
        "type": event_type,
        "data": {
            "load_id": load_id,
            "document_type": data.get("document_type"),
            "document_id": data.get("document_id"),
            "driver_id": data.get("driver_id"),
            "stop_id": data.get("stop_id"),
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
        }
    }
    await manager.send_company_message(message, company_id)


async def broadcast_equipment_update(equipment_id: str, company_id: str, event_type: str, data: dict) -> None:
    """Broadcast equipment-related updates."""
    message = {
        "type": "equipment_update",
        "data": {
            "equipment_id": equipment_id,
            "event_type": event_type,
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
            **data
        }
    }
    await manager.send_company_message(message, company_id)


async def send_user_notification(user_id: str, notification_type: str, data: dict) -> None:
    """Send a notification to a specific user."""
    message = {
        "type": "notification",
        "data": {
            "notification_type": notification_type,
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
            **data
        }
    }
    await manager.send_personal_message(message, user_id)


# ==================== DRIVER-SPECIFIC MESSAGING ====================

async def send_to_driver(driver_id: str, message_type: str, data: dict) -> None:
    """Send a message to a specific driver."""
    user_id = driver_connections.get(driver_id)
    if user_id:
        message = {
            "type": message_type,
            "data": {
                "timestamp": datetime.utcnow().isoformat(),
                **data
            }
        }
        await manager.send_personal_message(message, user_id)


async def notify_load_assigned(driver_id: str, load_data: dict) -> None:
    """Notify driver that a load has been assigned to them."""
    await send_to_driver(driver_id, "load_assigned", load_data)


async def notify_load_unassigned(driver_id: str, load_data: dict) -> None:
    """Notify driver that a load has been unassigned from them."""
    await send_to_driver(driver_id, "load_unassigned", load_data)


async def notify_truck_assigned(driver_id: str, equipment_data: dict) -> None:
    """Notify driver that a truck has been assigned to them."""
    await send_to_driver(driver_id, "truck_assigned", equipment_data)


async def notify_truck_unassigned(driver_id: str, equipment_data: dict) -> None:
    """Notify driver that a truck has been unassigned from them."""
    await send_to_driver(driver_id, "truck_unassigned", equipment_data)


async def notify_document_status(driver_id: str, status: str, document_data: dict) -> None:
    """Notify driver about document status (approved/rejected)."""
    await send_to_driver(driver_id, f"document_{status}", document_data)


# ==================== CHAT/MESSAGING ====================

async def handle_chat_message(data: dict, user, driver_id: Optional[str], db: AsyncSession) -> None:
    """Process and broadcast chat message from driver."""
    import uuid
    from app.models.collaboration import Channel, Message
    from app.websocket.hub import channel_hub

    # Accept both "message" (legacy) and "body" (frontend standard) field names
    message_body = data.get("message") or data.get("body", "")
    channel_id = data.get("channel_id")
    company_id = str(user.company_id)

    if not message_body:
        logger.warning(f"Empty chat message from user {user.id}")
        return

    # If no channel_id, get or create driver channel
    if not channel_id and driver_id:
        from app.services.webhook_chat import WebhookChatService
        chat_service = WebhookChatService(db)
        channel = await chat_service.get_or_create_driver_channel(company_id, driver_id)
        channel_id = channel.id

    if not channel_id:
        logger.warning(f"No channel for chat message from user {user.id}")
        return

    # Create message in database
    message = Message(
        id=str(uuid.uuid4()),
        channel_id=channel_id,
        author_id=str(user.id),
        body=message_body,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    # Broadcast message to channel
    message_data = {
        "id": message.id,
        "channel_id": message.channel_id,
        "author_id": message.author_id,
        "author_name": f"{user.first_name} {user.last_name}" if hasattr(user, 'first_name') else "Driver",
        "body": message.body,
        "created_at": message.created_at.isoformat(),
        "is_from_driver": True,
    }

    # Broadcast to channel hub (for web dashboard)
    await channel_hub.broadcast(channel_id, {
        "type": "message",
        "data": message_data,
    })

    # Also broadcast to company for dispatch notifications
    await manager.send_company_message({
        "type": "chat_message",
        "data": {
            **message_data,
            "driver_id": driver_id,
        }
    }, company_id)

    logger.info(f"Chat message sent by user {user.id} in channel {channel_id}")


async def send_message_history(websocket: WebSocket, data: dict, user, db: AsyncSession) -> None:
    """Send message history to driver."""
    from sqlalchemy import select
    from app.models.collaboration import Channel, Message
    from app.models.driver import Driver

    driver_id = data.get("driver_id")
    channel_id = data.get("channel_id")
    limit = data.get("limit", 50)
    company_id = str(user.company_id)

    # Get driver's channel if not provided
    if not channel_id and driver_id:
        result = await db.execute(
            select(Channel).where(
                Channel.company_id == company_id,
                Channel.name.like(f"driver:{driver_id}%")
            )
        )
        channel = result.scalar_one_or_none()
        if channel:
            channel_id = channel.id

    if not channel_id:
        await websocket.send_json({
            "type": "message_history",
            "data": {"messages": [], "channel_id": None}
        })
        return

    # Get messages
    result = await db.execute(
        select(Message)
        .where(Message.channel_id == channel_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())

    # Get author info for each message
    from app.models.user import User
    messages_data = []
    for msg in reversed(messages):  # Reverse to get chronological order
        # Get author name
        author_result = await db.execute(
            select(User).where(User.id == msg.author_id)
        )
        author = author_result.scalar_one_or_none()
        author_name = f"{author.first_name} {author.last_name}" if author else "System"

        # Check if message is from driver
        is_from_driver = False
        if driver_id:
            driver_result = await db.execute(
                select(Driver).where(Driver.id == driver_id, Driver.user_id == msg.author_id)
            )
            is_from_driver = driver_result.scalar_one_or_none() is not None

        messages_data.append({
            "id": msg.id,
            "channel_id": msg.channel_id,
            "author_id": msg.author_id,
            "author_name": author_name,
            "body": msg.body,
            "created_at": msg.created_at.isoformat(),
            "is_from_driver": is_from_driver,
        })

    await websocket.send_json({
        "type": "message_history",
        "data": {
            "channel_id": channel_id,
            "messages": messages_data,
        }
    })


async def handle_mark_read(data: dict, user, db: AsyncSession) -> None:
    """Mark messages as read (for read receipts - future use)."""
    # Placeholder for read receipt functionality
    pass


async def send_chat_to_driver(driver_id: str, message_data: dict) -> None:
    """Send a chat message to a specific driver."""
    await send_to_driver(driver_id, "chat_message", message_data)
