from typing import Dict, Set, Optional, Any
from fastapi import WebSocket
import json


class ConnectionManager:
    """In-memory WebSocket connection manager scoped by tenant and conversation.

    NOTE: This is a simple, single-process manager suitable for dev/single-instance.
    For multi-instance deployments, replace with a shared pub/sub (e.g., Redis).
    """

    def __init__(self) -> None:
        self.tenant_connections: Dict[str, Set[WebSocket]] = {}
        self.conversation_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, tenant_id: str) -> None:
        await websocket.accept()
        self.tenant_connections.setdefault(tenant_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, tenant_id: Optional[str] = None) -> None:
        if tenant_id and tenant_id in self.tenant_connections:
            self.tenant_connections[tenant_id].discard(websocket)
            if not self.tenant_connections[tenant_id]:
                del self.tenant_connections[tenant_id]
        # Remove from all conversations
        to_delete = []
        for conv_id, sockets in self.conversation_connections.items():
            sockets.discard(websocket)
            if not sockets:
                to_delete.append(conv_id)
        for conv_id in to_delete:
            del self.conversation_connections[conv_id]

    def subscribe_conversation(self, websocket: WebSocket, conversation_id: str) -> None:
        self.conversation_connections.setdefault(conversation_id, set()).add(websocket)

    async def broadcast_to_tenant(self, tenant_id: str, event: Dict[str, Any]) -> None:
        message = json.dumps(event, default=str)
        for ws in list(self.tenant_connections.get(tenant_id, set())):
            try:
                await ws.send_text(message)
            except Exception:
                # Best-effort cleanup on failures
                self.disconnect(ws, tenant_id)

    async def broadcast_to_conversation(self, conversation_id: str, event: Dict[str, Any]) -> None:
        message = json.dumps(event, default=str)
        for ws in list(self.conversation_connections.get(conversation_id, set())):
            try:
                await ws.send_text(message)
            except Exception:
                # Best-effort cleanup
                self.conversation_connections.get(conversation_id, set()).discard(ws)


ws_manager = ConnectionManager()




