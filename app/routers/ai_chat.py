"""
AI Chat Router - Conversational API endpoints for AI agents.

Users can chat directly with Annie, Adam, and Atlas like talking to employees.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.db import get_db
from app.services.conversational_ai import ConversationalAI
from app.models.ai_chat import AIConversation, AIMessage


router = APIRouter(prefix="/ai/chat", tags=["AI Chat"])


class ChatInitRequest(BaseModel):
    session_id: str
    company_id: str
    user_id: str
    user_name: str
    agent: str  # annie, adam, felix, harper, or atlas


class ChatMessageRequest(BaseModel):
    session_id: str
    company_id: str
    user_id: str
    user_name: str
    agent: str
    message: str
    context: Optional[List[Dict]] = None


class ChatResponse(BaseModel):
    message: str
    agent: str
    reasoning: Optional[str] = None
    tools_used: Optional[List[str]] = None
    task_id: Optional[str] = None
    delegated_to: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatHistoryMessage(BaseModel):
    id: str
    role: str
    content: str
    assistant_type: Optional[str] = None
    tokens_used: Optional[int] = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatHistoryMessage]
    total: int


async def _get_or_create_conversation(
    db: AsyncSession,
    session_id: str,
    company_id: str,
    user_id: str,
    agent: str,
) -> AIConversation:
    """Get existing conversation or create a new one."""
    result = await db.execute(
        select(AIConversation).where(
            AIConversation.id == session_id,
            AIConversation.company_id == company_id,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = AIConversation(
            id=session_id,
            company_id=company_id,
            user_id=user_id,
            assistant_type=agent,
            status="active",
            message_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_message_at=datetime.utcnow(),
        )
        db.add(conversation)
        await db.flush()

    return conversation


async def _save_message(
    db: AsyncSession,
    conversation: AIConversation,
    role: str,
    content: str,
    assistant_type: Optional[str] = None,
    user_id: Optional[str] = None,
    tokens_used: Optional[int] = None,
    model: Optional[str] = None,
    tool_calls: Optional[List] = None,
    confidence_score: Optional[int] = None,
) -> AIMessage:
    """Save a message to the conversation."""
    message = AIMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        company_id=conversation.company_id,
        role=role,
        content=content,
        assistant_type=assistant_type,
        user_id=user_id,
        tokens_used=tokens_used,
        model=model,
        tool_calls=tool_calls,
        confidence_score=confidence_score,
        created_at=datetime.utcnow(),
    )
    db.add(message)

    # Update conversation stats
    conversation.message_count += 1
    conversation.last_message_at = datetime.utcnow()
    conversation.updated_at = datetime.utcnow()

    return message


@router.post("/init", response_model=ChatResponse)
async def initialize_chat(
    request: ChatInitRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initialize a chat session with an AI agent.

    The agent will send a personalized greeting.
    """

    conversational_ai = ConversationalAI(
        db=db,
        company_id=request.company_id,
        user_id=request.user_id,
        user_name=request.user_name
    )

    # Generate greeting
    agent_names = {
        "annie": "Annie",
        "adam": "Adam",
        "felix": "Felix",
        "harper": "Harper",
        "atlas": "Atlas"
    }

    hour = datetime.utcnow().hour
    if hour < 12:
        time_greeting = "Good morning"
    elif hour < 18:
        time_greeting = "Good afternoon"
    else:
        time_greeting = "Good evening"

    greeting = f"{time_greeting}, {request.user_name}! I'm {agent_names.get(request.agent, 'AI')}, your {request.agent.capitalize()} agent. How can I help you today?"

    # Create conversation and save initial greeting
    conversation = await _get_or_create_conversation(
        db=db,
        session_id=request.session_id,
        company_id=request.company_id,
        user_id=request.user_id,
        agent=request.agent,
    )

    await _save_message(
        db=db,
        conversation=conversation,
        role="assistant",
        content=greeting,
        assistant_type=request.agent,
        confidence_score=100,
    )

    await db.commit()

    return ChatResponse(
        message=greeting,
        agent=request.agent,
        reasoning=f"Personalized greeting for {request.user_name}",
        confidence=1.0,
        metadata={
            "session_id": request.session_id,
            "initialized_at": datetime.utcnow().isoformat()
        }
    )


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to an AI agent and get conversational response.

    Examples:
    - "Good morning Annie" → Personalized greeting
    - "What's the weather in Chicago?" → Weather data
    - "How's traffic near truck 110?" → Truck location + traffic
    - "Create 20 loads" → Bulk load creation
    """

    # Get or create conversation
    conversation = await _get_or_create_conversation(
        db=db,
        session_id=request.session_id,
        company_id=request.company_id,
        user_id=request.user_id,
        agent=request.agent,
    )

    # Save user message
    await _save_message(
        db=db,
        conversation=conversation,
        role="user",
        content=request.message,
        user_id=request.user_id,
    )

    conversational_ai = ConversationalAI(
        db=db,
        company_id=request.company_id,
        user_id=request.user_id,
        user_name=request.user_name
    )

    # Process the message
    result = await conversational_ai.process_message(
        agent_type=request.agent,
        message=request.message,
        session_id=request.session_id,
        context=request.context
    )

    # Save assistant response
    await _save_message(
        db=db,
        conversation=conversation,
        role="assistant",
        content=result["response"],
        assistant_type=result.get("agent", request.agent),
        tokens_used=result.get("tokens_used"),
        model=result.get("model"),
        tool_calls=result.get("tools_used"),
        confidence_score=int(result.get("confidence", 0) * 100) if result.get("confidence") else None,
    )

    await db.commit()

    return ChatResponse(
        message=result["response"],
        agent=result.get("agent", request.agent),
        reasoning=result.get("reasoning"),
        tools_used=result.get("tools_used"),
        task_id=result.get("task_id"),
        delegated_to=result.get("delegated_to"),
        confidence=result.get("confidence"),
        metadata={
            "model": result.get("model"),
            "tokens_used": result.get("tokens_used"),
            "cost_usd": result.get("cost_usd"),
            "data": result.get("data")
        }
    )


@router.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    company_id: str = Query(..., description="Company ID for authorization"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat history for a session.
    """

    # Verify conversation exists and belongs to company
    conv_result = await db.execute(
        select(AIConversation).where(
            AIConversation.id == session_id,
            AIConversation.company_id == company_id,
        )
    )
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        return ChatHistoryResponse(
            session_id=session_id,
            messages=[],
            total=0,
        )

    # Fetch messages
    messages_result = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == session_id)
        .order_by(AIMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    messages = messages_result.scalars().all()

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[
            ChatHistoryMessage(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                assistant_type=msg.assistant_type,
                tokens_used=msg.tokens_used,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
        total=conversation.message_count,
    )


@router.get("/conversations")
async def list_conversations(
    company_id: str = Query(..., description="Company ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    assistant_type: Optional[str] = Query(None, description="Filter by assistant type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    List recent conversations for a company.
    """

    query = (
        select(AIConversation)
        .where(AIConversation.company_id == company_id)
        .order_by(AIConversation.last_message_at.desc())
    )

    if user_id:
        query = query.where(AIConversation.user_id == user_id)

    if assistant_type:
        query = query.where(AIConversation.assistant_type == assistant_type)

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    conversations = result.scalars().all()

    return {
        "conversations": [
            {
                "id": conv.id,
                "user_id": conv.user_id,
                "assistant_type": conv.assistant_type,
                "title": conv.title,
                "status": conv.status,
                "message_count": conv.message_count,
                "last_message_at": conv.last_message_at,
                "created_at": conv.created_at,
            }
            for conv in conversations
        ],
        "total": len(conversations),
    }
