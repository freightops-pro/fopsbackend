"""HQ WebSocket connection manager for real-time chat updates."""
import asyncio
import logging
from typing import Dict, List, Set
from fastapi import WebSocket
from app.models.hq_employee import HQEmployee

logger = logging.getLogger(__name__)


class HQConnectionManager:
    """Manages WebSocket connections for HQ employees."""

    def __init__(self):
        # Map of employee_id to list of WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Map of channel_id to set of employee_ids subscribed to that channel
        self.channel_subscribers: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, employee: HQEmployee) -> None:
        """Register a WebSocket connection (already accepted)."""
        async with self._lock:
            employee_id = str(employee.id)

            # Add connection to employee's connection list
            if employee_id not in self.active_connections:
                self.active_connections[employee_id] = []
            self.active_connections[employee_id].append(websocket)

            logger.info(f"HQ WebSocket connected - Employee: {employee.email} ({employee_id})")
            logger.debug(f"HQ Active connections: {len(self.active_connections)} employees, {sum(len(conns) for conns in self.active_connections.values())} total connections")

    async def disconnect(self, websocket: WebSocket, employee: HQEmployee) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            employee_id = str(employee.id)

            # Remove connection from employee's connection list
            if employee_id in self.active_connections:
                if websocket in self.active_connections[employee_id]:
                    self.active_connections[employee_id].remove(websocket)

                # Clean up if no more connections for this employee
                if not self.active_connections[employee_id]:
                    del self.active_connections[employee_id]

                    # Remove employee from all channel subscriptions
                    for channel_id in list(self.channel_subscribers.keys()):
                        self.channel_subscribers[channel_id].discard(employee_id)
                        if not self.channel_subscribers[channel_id]:
                            del self.channel_subscribers[channel_id]

            logger.info(f"HQ WebSocket disconnected - Employee: {employee.email} ({employee_id})")
            logger.debug(f"HQ Active connections: {len(self.active_connections)} employees")

    async def subscribe_to_channel(self, employee_id: str, channel_id: str) -> None:
        """Subscribe an employee to a channel for real-time updates."""
        async with self._lock:
            if channel_id not in self.channel_subscribers:
                self.channel_subscribers[channel_id] = set()
            self.channel_subscribers[channel_id].add(employee_id)
            logger.debug(f"Employee {employee_id} subscribed to channel {channel_id}")

    async def unsubscribe_from_channel(self, employee_id: str, channel_id: str) -> None:
        """Unsubscribe an employee from a channel."""
        async with self._lock:
            if channel_id in self.channel_subscribers:
                self.channel_subscribers[channel_id].discard(employee_id)
                if not self.channel_subscribers[channel_id]:
                    del self.channel_subscribers[channel_id]
            logger.debug(f"Employee {employee_id} unsubscribed from channel {channel_id}")

    async def send_personal_message(self, message: dict, employee_id: str) -> None:
        """Send a message to all connections of a specific employee."""
        if employee_id not in self.active_connections:
            logger.debug(f"No active HQ connections for employee {employee_id}")
            return

        connections = self.active_connections[employee_id].copy()
        disconnected = []

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send HQ message to employee {employee_id}: {e}")
                disconnected.append(connection)

        # Clean up disconnected connections
        if disconnected:
            async with self._lock:
                for conn in disconnected:
                    if employee_id in self.active_connections and conn in self.active_connections[employee_id]:
                        self.active_connections[employee_id].remove(conn)
                if employee_id in self.active_connections and not self.active_connections[employee_id]:
                    del self.active_connections[employee_id]

    async def broadcast_to_channel(self, message: dict, channel_id: str) -> None:
        """Broadcast a message to all employees subscribed to a channel."""
        if channel_id not in self.channel_subscribers:
            logger.debug(f"No subscribers for HQ channel {channel_id}")
            return

        employee_ids = self.channel_subscribers[channel_id].copy()

        for employee_id in employee_ids:
            await self.send_personal_message(message, employee_id)

    async def broadcast_to_all(self, message: dict) -> None:
        """Broadcast a message to all connected HQ employees."""
        employee_ids = list(self.active_connections.keys())

        for employee_id in employee_ids:
            await self.send_personal_message(message, employee_id)

    def get_connection_count(self) -> int:
        """Get total number of active HQ WebSocket connections."""
        return sum(len(conns) for conns in self.active_connections.values())

    def get_employee_count(self) -> int:
        """Get number of unique HQ employees with active connections."""
        return len(self.active_connections)

    def is_employee_connected(self, employee_id: str) -> bool:
        """Check if an employee has any active connections."""
        return employee_id in self.active_connections and len(self.active_connections[employee_id]) > 0


# Global HQ connection manager instance
hq_manager = HQConnectionManager()
