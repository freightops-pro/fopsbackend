"""
AI Chat Router - Conversational API endpoints for AI agents.

Users can chat directly with Annie, Adam, and Atlas like talking to employees.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.db import get_db
from app.services.conversational_ai import ConversationalAI


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


@router.get("/sessions/{session_id}/history")
async def get_chat_history(
    session_id: str,
    company_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat history for a session.
    """

    # TODO: Store chat messages in database for persistence
    # For now, return empty array (messages are stored client-side)

    return {
        "session_id": session_id,
        "messages": [],
        "note": "Chat history persistence coming soon"
    }
