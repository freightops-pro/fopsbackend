from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.user import User
from app.models.driver import Driver
from app.schemas.collaboration import (
    ChannelCreate,
    ChannelDetailResponse,
    ChannelResponse,
    GroupChatCreate,
    MessageCreate,
    MessageResponse,
)
from app.schemas.presence import PresenceState, PresenceUpdate, SetAwayMessage
from app.services.collaboration import CollaborationService
from app.services.presence import PresenceService
from app.websocket.hub import channel_hub

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> CollaborationService:
    return CollaborationService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


async def _user_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.id


async def _presence_service(db: AsyncSession = Depends(get_db)) -> PresenceService:
    return PresenceService(db)


@router.get("/channels", response_model=List[ChannelResponse])
async def list_channels(
    company_id: str = Depends(_company_id),
    service: CollaborationService = Depends(_service),
    driver_id: Optional[str] = Query(None, description="Filter channels by driver ID"),
) -> List[ChannelResponse]:
    """
    List all channels for the company with participants.
    Optionally filter by driver_id to get driver-specific channels.
    """
    return await service.list_channels(company_id, driver_id=driver_id)


@router.post("/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    payload: ChannelCreate,
    company_id: str = Depends(_company_id),
    service: CollaborationService = Depends(_service),
) -> ChannelResponse:
    return await service.create_channel(company_id, payload)


@router.post("/channels/group", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_group_chat(
    payload: GroupChatCreate,
    company_id: str = Depends(_company_id),
    current_user_id: str = Depends(_user_id),
    service: CollaborationService = Depends(_service),
) -> ChannelResponse:
    """
    Create a group chat with multiple participants.
    """
    return await service.create_group_chat(company_id, current_user_id, payload)


@router.get("/channels/{channel_id}", response_model=ChannelDetailResponse)
async def get_channel_detail(
    channel_id: str,
    company_id: str = Depends(_company_id),
    service: CollaborationService = Depends(_service),
) -> ChannelDetailResponse:
    try:
        return await service.channel_detail(company_id, channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_channel(
    channel_id: str,
    company_id: str = Depends(_company_id),
    service: CollaborationService = Depends(_service),
) -> None:
    """
    Delete a channel and all its messages.
    """
    try:
        await service.delete_channel(company_id, channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/drivers/{driver_id}/channel", response_model=ChannelResponse)
async def get_driver_channel(
    driver_id: str,
    company_id: str = Depends(_company_id),
    service: CollaborationService = Depends(_service),
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """
    Get or create a channel for driver communication.
    """
    # Get driver name
    result = await db.execute(
        select(Driver).where(Driver.id == driver_id, Driver.company_id == company_id)
    )
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )

    driver_name = f"{driver.first_name} {driver.last_name}"
    return await service.get_or_create_driver_channel(company_id, driver_id, driver_name)


@router.post("/users/{target_user_id}/channel", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def get_or_create_user_channel(
    target_user_id: str,
    company_id: str = Depends(_company_id),
    current_user_id: str = Depends(_user_id),
    service: CollaborationService = Depends(_service),
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """
    Get or create a direct message channel with another user.
    Returns the existing channel if one already exists.
    """
    # Verify target user exists and belongs to same company
    result = await db.execute(
        select(User).where(User.id == target_user_id, User.company_id == company_id)
    )
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get current user for display name
    current_result = await db.execute(select(User).where(User.id == current_user_id))
    current_user = current_result.scalar_one_or_none()

    current_user_name = f"{current_user.first_name} {current_user.last_name}" if current_user else "Unknown"
    target_user_name = f"{target_user.first_name} {target_user.last_name}"

    return await service.get_or_create_dm_channel(
        company_id, current_user_id, target_user_id, current_user_name, target_user_name
    )


@router.get("/channels/{channel_id}/messages", response_model=List[MessageResponse])
async def get_channel_messages(
    channel_id: str,
    company_id: str = Depends(_company_id),
    service: CollaborationService = Depends(_service),
) -> List[MessageResponse]:
    """
    Get all messages for a channel.
    """
    try:
        await service.get_channel(company_id, channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    messages = await service.list_messages(channel_id)
    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/channels/{channel_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def post_message(
    channel_id: str,
    payload: MessageCreate,
    company_id: str = Depends(_company_id),
    author_id: str = Depends(_user_id),
    service: CollaborationService = Depends(_service),
) -> MessageResponse:
    # ensure channel belongs to company
    try:
        await service.get_channel(company_id, channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    message = await service.post_message(channel_id, author_id, payload)
    response = MessageResponse.model_validate(message)
    await channel_hub.broadcast(
        channel_id,
        {
            "type": "message",
            "data": response.model_dump(),
        },
    )
    return response


# ============ Presence REST Endpoints ============

@router.get("/channels/{channel_id}/presence", response_model=List[PresenceState])
async def get_channel_presence(
    channel_id: str,
    company_id: str = Depends(_company_id),
    service: CollaborationService = Depends(_service),
    presence_service: PresenceService = Depends(_presence_service),
) -> List[PresenceState]:
    """Get presence status for all users in a channel."""
    try:
        await service.get_channel(company_id, channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return await presence_service.current_presence(channel_id)


@router.put("/channels/{channel_id}/presence", response_model=PresenceState)
async def update_presence(
    channel_id: str,
    payload: PresenceUpdate,
    company_id: str = Depends(_company_id),
    user_id: str = Depends(_user_id),
    service: CollaborationService = Depends(_service),
    presence_service: PresenceService = Depends(_presence_service),
) -> PresenceState:
    """Update user's presence status in a channel."""
    try:
        await service.get_channel(company_id, channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    # Manual status update (user explicitly set it)
    state = await presence_service.set_presence(
        channel_id, user_id, payload.status, payload.away_message, manual=True
    )

    # Broadcast presence update
    await channel_hub.broadcast(
        channel_id,
        {
            "type": "presence",
            "data": [s.model_dump() for s in await presence_service.current_presence(channel_id)],
        },
    )
    return state


@router.post("/channels/{channel_id}/presence/heartbeat", response_model=PresenceState)
async def presence_heartbeat(
    channel_id: str,
    company_id: str = Depends(_company_id),
    user_id: str = Depends(_user_id),
    service: CollaborationService = Depends(_service),
    presence_service: PresenceService = Depends(_presence_service),
) -> PresenceState:
    """Send heartbeat to indicate user activity. Updates last_activity_at."""
    try:
        await service.get_channel(company_id, channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    state = await presence_service.update_activity(channel_id, user_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presence not found")
    return state


@router.put("/channels/{channel_id}/presence/away-message", response_model=PresenceState)
async def set_away_message(
    channel_id: str,
    payload: SetAwayMessage,
    company_id: str = Depends(_company_id),
    user_id: str = Depends(_user_id),
    service: CollaborationService = Depends(_service),
    presence_service: PresenceService = Depends(_presence_service),
) -> PresenceState:
    """Set or clear user's away message."""
    try:
        await service.get_channel(company_id, channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    state = await presence_service.set_away_message(channel_id, user_id, payload.away_message)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presence not found")

    # Broadcast presence update
    await channel_hub.broadcast(
        channel_id,
        {
            "type": "presence",
            "data": [s.model_dump() for s in await presence_service.current_presence(channel_id)],
        },
    )
    return state


@router.websocket("/channels/{channel_id}/ws")
async def collaboration_stream(
    websocket: WebSocket,
    channel_id: str,
    presence_service: PresenceService = Depends(_presence_service),
    db: AsyncSession = Depends(get_db),
):
    """WebSocket connection for real-time channel updates.

    Handles incoming messages:
    - {"type": "presence", "status": "online|away|offline", "away_message": "..."}
    - {"type": "heartbeat"} - Updates activity timestamp
    """
    import json

    user = await deps.get_current_user_websocket(websocket, db)
    await channel_hub.connect(channel_id, websocket)
    try:
        # Set user as online on connect
        await presence_service.set_presence(channel_id, user.id, "online")
        await channel_hub.broadcast(
            channel_id,
            {
                "type": "presence",
                "data": [state.model_dump() for state in await presence_service.current_presence(channel_id)],
            },
        )
        while True:
            payload = await websocket.receive_text()
            try:
                data = json.loads(payload)
                msg_type = data.get("type", "presence")

                if msg_type == "heartbeat":
                    # Activity heartbeat - just update timestamp, don't broadcast
                    await presence_service.update_activity(channel_id, user.id)
                elif msg_type == "presence":
                    # Presence update
                    update = PresenceUpdate.model_validate(data)
                    # User manually setting status
                    await presence_service.set_presence(
                        channel_id, user.id, update.status, update.away_message, manual=True
                    )
                    await channel_hub.broadcast(
                        channel_id,
                        {
                            "type": "presence",
                            "data": [state.model_dump() for state in await presence_service.current_presence(channel_id)],
                        },
                    )
            except Exception:
                continue
    except WebSocketDisconnect:
        channel_hub.disconnect(channel_id, websocket)
        await presence_service.mark_user_offline(channel_id, user.id)
        await channel_hub.broadcast(
            channel_id,
            {
                "type": "presence",
                "data": [state.model_dump() for state in await presence_service.current_presence(channel_id)],
            },
        )
