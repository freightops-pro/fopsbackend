import json
from typing import Dict, Set

from fastapi import WebSocket


class ChannelHub:
    def __init__(self) -> None:
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, channel_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(channel_id, set()).add(websocket)

    def disconnect(self, channel_id: str, websocket: WebSocket) -> None:
        clients = self.connections.get(channel_id)
        if not clients:
            return
        clients.discard(websocket)
        if not clients:
            self.connections.pop(channel_id, None)

    async def broadcast(self, channel_id: str, message: dict) -> None:
        payload = json.dumps(message)
        for connection in self.connections.get(channel_id, set()):
            await connection.send_text(payload)


channel_hub = ChannelHub()

