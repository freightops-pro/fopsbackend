from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.config.db import get_db
from app.services.chat_service import ChatService
from app.schema.chatSchema import (
    ConversationCreateRequest, ConversationResponse,
    ConversationListResponse, MessageCreateRequest, 
    MessageResponse, MessageWithDetailsResponse
)
from app.routes.user import get_current_user
from app.models.userModels import Users

# Setup logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# Dependency to get chat service
def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)

# Conversation Routes

@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreateRequest,
    chat_service: ChatService = Depends(get_chat_service),
    current_user: Users = Depends(get_current_user)
):
    """Create a new conversation between users and/or drivers"""
    try:
        conversation = await chat_service.create_conversation(
            company_id=current_user.companyid,
            participant_id=current_user.id,
            participant_type="user",
            conversation_data=conversation_data
        )
        logger.info(f"Conversation created: {conversation.id} by user: {current_user.id}")
        return conversation
    except ValueError as e:
        logger.error(f"Validation error creating conversation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create conversation")

@router.get("/conversations", response_model=List[ConversationListResponse])
async def get_participant_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    chat_service: ChatService = Depends(get_chat_service),
    current_user: Users = Depends(get_current_user)
):
    """Get conversations for the current participant"""
    try:
        conversations = await chat_service.get_participant_conversations(
            participant_id=current_user.id,
            participant_type="user",
            company_id=current_user.companyid,
            limit=limit,
            offset=offset
        )
        return conversations
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get conversations")

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    chat_service: ChatService = Depends(get_chat_service),
    current_user: Users = Depends(get_current_user)
):
    """Get a specific conversation"""
    try:
        conversation = await chat_service.get_conversation(
            conversation_id=conversation_id,
            company_id=current_user.companyid
        )
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get conversation")

# Message Routes

@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreateRequest,
    chat_service: ChatService = Depends(get_chat_service),
    current_user: Users = Depends(get_current_user)
):
    """Create a new message"""
    try:
        message = await chat_service.create_message(
            company_id=current_user.companyid,
            participant_id=current_user.id,
            participant_type="user",
            message_data=message_data
        )
        logger.info(f"Message created: {message.id} by user: {current_user.id}")
        return message
    except ValueError as e:
        logger.error(f"Validation error creating message: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating message: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create message")

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageWithDetailsResponse])
async def get_conversation_messages(
    conversation_id: str = Path(..., description="Conversation ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    chat_service: ChatService = Depends(get_chat_service),
    current_user: Users = Depends(get_current_user)
):
    """Get messages for a conversation"""
    try:
        messages = await chat_service.get_conversation_messages(
            conversation_id=conversation_id,
            participant_id=current_user.id,
            participant_type="user",
            company_id=current_user.companyid,
            limit=limit,
            offset=offset
        )
        return messages
    except ValueError as e:
        logger.error(f"Validation error getting messages: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get messages")

# Health Check
@router.get("/health")
async def chat_health_check():
    """Health check for chat service"""
    return {"status": "healthy", "service": "chat"}
