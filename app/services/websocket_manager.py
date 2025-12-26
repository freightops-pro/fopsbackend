"""WebSocket connection manager for real-time updates."""
import asyncio
import logging
from typing import Dict, List, Set
from fastapi import WebSocket
from app.models.user import User

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        # Map of user_id to list of WebSocket connections (users can have multiple devices/tabs)
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Map of company_id to set of user_ids (for company-wide broadcasts)
        self.company_users: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user: User) -> None:
        """Register a WebSocket connection (already accepted by router)."""
        async with self._lock:
            user_id = str(user.id)
            company_id = str(user.company_id) if user.company_id else None

            # Add connection to user's connection list
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)

            # Track user in company mapping
            if company_id:
                if company_id not in self.company_users:
                    self.company_users[company_id] = set()
                self.company_users[company_id].add(user_id)

            logger.debug(f"WebSocket connected - User: {user_id}")

    async def disconnect(self, websocket: WebSocket, user: User) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            user_id = str(user.id)
            company_id = str(user.company_id) if user.company_id else None

            # Remove connection from user's connection list
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(websocket)

                # Clean up if no more connections for this user
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]

                    # Remove user from company mapping if no more connections
                    if company_id and company_id in self.company_users:
                        self.company_users[company_id].discard(user_id)
                        if not self.company_users[company_id]:
                            del self.company_users[company_id]

            logger.debug(f"WebSocket disconnected - User: {user_id}")

    async def send_personal_message(self, message: dict, user_id: str) -> None:
        """Send a message to all connections of a specific user."""
        if user_id not in self.active_connections:
            return

        connections = self.active_connections[user_id].copy()
        disconnected = []

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected connections
        if disconnected:
            async with self._lock:
                for conn in disconnected:
                    if user_id in self.active_connections and conn in self.active_connections[user_id]:
                        self.active_connections[user_id].remove(conn)
                if user_id in self.active_connections and not self.active_connections[user_id]:
                    del self.active_connections[user_id]

    async def send_company_message(self, message: dict, company_id: str) -> None:
        """Send a message to all users in a company."""
        if company_id not in self.company_users:
            return

        user_ids = self.company_users[company_id].copy()

        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected users."""
        user_ids = list(self.active_connections.keys())

        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

    def get_connection_count(self) -> int:
        """Get total number of active WebSocket connections."""
        return sum(len(conns) for conns in self.active_connections.values())

    def get_user_count(self) -> int:
        """Get number of unique users with active connections."""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()
