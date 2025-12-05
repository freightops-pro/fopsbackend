"""
Event dispatcher for decoupled real-time updates.

This pattern separates business logic from notification logic,
making the code more maintainable and testable.

Usage in services:
    from app.services.event_dispatcher import emit_event, EventType

    # Emit an event after business operation completes
    await emit_event(EventType.LOAD_ASSIGNED, {
        "driver_id": driver_id,
        "load_id": load_id,
        "company_id": company_id,
        ...
    })

The WebSocket layer subscribes to these events and handles broadcasting.
"""
import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types for real-time updates."""
    # Driver events
    DRIVER_CREATED = "driver.created"
    DRIVER_UPDATED = "driver.updated"
    DRIVER_DELETED = "driver.deleted"
    DRIVER_STATUS_CHANGED = "driver.status_changed"
    DRIVER_LOCATION_UPDATED = "driver.location_updated"

    # Load events
    LOAD_CREATED = "load.created"
    LOAD_UPDATED = "load.updated"
    LOAD_DELETED = "load.deleted"
    LOAD_STATUS_CHANGED = "load.status_changed"
    LOAD_ASSIGNED = "load.assigned"
    LOAD_UNASSIGNED = "load.unassigned"

    # Stop events
    DRIVER_ARRIVED = "stop.driver_arrived"
    DRIVER_DEPARTED = "stop.driver_departed"

    # Document events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_APPROVED = "document.approved"
    DOCUMENT_REJECTED = "document.rejected"

    # Equipment events
    EQUIPMENT_UPDATED = "equipment.updated"
    EQUIPMENT_ASSIGNED = "equipment.assigned"
    EQUIPMENT_UNASSIGNED = "equipment.unassigned"
    EQUIPMENT_INSPECTION = "equipment.inspection"

    # Chat/Message events
    MESSAGE_SENT = "message.sent"
    MESSAGE_RECEIVED = "message.received"
    CHANNEL_CREATED = "channel.created"


@dataclass
class Event:
    """Represents an event to be dispatched."""
    type: EventType
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    company_id: Optional[str] = None
    target_user_id: Optional[str] = None
    target_driver_id: Optional[str] = None


# Type for event handlers
EventHandler = Callable[[Event], Any]


class EventDispatcher:
    """
    Central event dispatcher for real-time updates.

    Implements a simple pub/sub pattern for decoupling
    business logic from notification logic.
    """

    _instance: Optional["EventDispatcher"] = None
    _handlers: Dict[EventType, List[EventHandler]]
    _global_handlers: List[EventHandler]

    def __new__(cls) -> "EventDispatcher":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = {}
            cls._instance._global_handlers = []
        return cls._instance

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to {event_type.value}")

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all events."""
        self._global_handlers.append(handler)
        logger.debug("Global handler subscribed")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from a specific event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def emit(self, event: Event) -> None:
        """Emit an event to all subscribers."""
        handlers = self._handlers.get(event.type, []) + self._global_handlers

        if not handlers:
            logger.debug(f"No handlers for event {event.type.value}")
            return

        # Run handlers concurrently
        tasks = []
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    tasks.append(result)
            except Exception as e:
                logger.error(f"Error in event handler for {event.type.value}: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.debug(f"Event {event.type.value} dispatched to {len(handlers)} handlers")


# Global dispatcher instance
_dispatcher = EventDispatcher()


def get_dispatcher() -> EventDispatcher:
    """Get the global event dispatcher."""
    return _dispatcher


async def emit_event(
    event_type: EventType,
    data: Dict[str, Any],
    company_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    target_driver_id: Optional[str] = None,
) -> None:
    """
    Emit an event to all subscribers.

    This is the main function services should use to emit events.

    Args:
        event_type: Type of event
        data: Event data payload
        company_id: Company to broadcast to (for company-wide events)
        target_user_id: Specific user to send to (for personal notifications)
        target_driver_id: Specific driver to send to
    """
    event = Event(
        type=event_type,
        data=data,
        company_id=company_id,
        target_user_id=target_user_id,
        target_driver_id=target_driver_id,
    )
    await _dispatcher.emit(event)


def subscribe(event_type: EventType, handler: EventHandler) -> None:
    """Subscribe a handler to an event type."""
    _dispatcher.subscribe(event_type, handler)


def subscribe_all(handler: EventHandler) -> None:
    """Subscribe a handler to all events."""
    _dispatcher.subscribe_all(handler)
