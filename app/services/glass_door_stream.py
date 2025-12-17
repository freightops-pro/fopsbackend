"""
Glass Door Stream Service - Real-time visibility into AI thinking.

Broadcasts agent thoughts, decisions, and actions to WebSocket clients.
"""

import uuid
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text


class GlassDoorStream:
    """
    Provides real-time visibility into AI agent execution.

    Like watching through a glass door - you can see everything happening.
    """

    def __init__(self, db: AsyncSession, task_id: str, company_id: str):
        self.db = db
        self.task_id = task_id
        self.company_id = company_id

    async def log_thinking(
        self,
        agent_type: str,
        thought: str,
        reasoning: str = None,
        metadata: dict = None
    ):
        """
        Log an agent's thought process.

        Example:
            await stream.log_thinking(
                "annie",
                "Analyzing rate confirmation PDF...",
                reasoning="Need to extract origin, destination, and rate",
                metadata={"pdf_url": "..."}
            )
        """
        await self._log_event(
            agent_type=agent_type,
            event_type="thinking",
            message=thought,
            reasoning=reasoning,
            metadata=metadata,
            severity="info"
        )

    async def log_tool_call(
        self,
        agent_type: str,
        tool_name: str,
        parameters: dict,
        reasoning: str = None
    ):
        """Log when an agent calls a tool/function."""
        await self._log_event(
            agent_type=agent_type,
            event_type="tool_call",
            message=f"Calling tool: {tool_name}",
            reasoning=reasoning,
            metadata={"tool": tool_name, "parameters": parameters},
            severity="info"
        )

    async def log_decision(
        self,
        agent_type: str,
        decision: str,
        reasoning: str,
        confidence: float = None,
        alternatives_considered: list = None
    ):
        """Log an agent's decision."""
        await self._log_event(
            agent_type=agent_type,
            event_type="decision",
            message=decision,
            reasoning=reasoning,
            metadata={
                "confidence": confidence,
                "alternatives": alternatives_considered
            },
            severity="success"
        )

    async def log_rejection(
        self,
        agent_type: str,
        rejected_action: str,
        reason: str,
        suggested_alternative: str = None
    ):
        """Log when one agent rejects another's proposal."""
        await self._log_event(
            agent_type=agent_type,
            event_type="rejection",
            message=f"REJECTED: {rejected_action}",
            reasoning=reason,
            metadata={"suggested_alternative": suggested_alternative},
            severity="warning"
        )

    async def log_error(
        self,
        agent_type: str,
        error: str,
        context: dict = None
    ):
        """Log an error during execution."""
        await self._log_event(
            agent_type=agent_type,
            event_type="error",
            message=error,
            metadata=context,
            severity="error"
        )

    async def log_result(
        self,
        agent_type: str,
        result: str,
        data: dict = None
    ):
        """Log the final result of an action."""
        await self._log_event(
            agent_type=agent_type,
            event_type="result",
            message=result,
            metadata=data,
            severity="success"
        )

    async def _log_event(
        self,
        agent_type: str,
        event_type: str,
        message: str,
        reasoning: str = None,
        metadata: dict = None,
        severity: str = "info"
    ):
        """Internal: Log event to database and broadcast via WebSocket."""
        # Save to database
        event_id = str(uuid.uuid4())

        # Convert metadata to JSON string if present
        metadata_json = json.dumps(metadata) if metadata else None

        # Insert into ai_agent_stream table
        await self.db.execute(
            text("""
            INSERT INTO ai_agent_stream
            (id, task_id, company_id, agent_type, event_type, message, reasoning, metadata, severity, created_at)
            VALUES
            (:id, :task_id, :company_id, :agent_type, :event_type, :message, :reasoning, :metadata::jsonb, :severity, :created_at)
            """),
            {
                "id": event_id,
                "task_id": self.task_id,
                "company_id": self.company_id,
                "agent_type": agent_type,
                "event_type": event_type,
                "message": message,
                "reasoning": reasoning,
                "metadata": metadata_json,
                "severity": severity,
                "created_at": datetime.utcnow()
            }
        )
        await self.db.commit()

        # Broadcast via WebSocket to all clients watching this task
        try:
            # Import WebSocket manager dynamically to avoid circular imports
            from app.services.websocket_manager import manager

            await manager.send_company_message(
                message={
                    "type": "ai_agent_stream",
                    "data": {
                        "task_id": self.task_id,
                        "agent_type": agent_type,
                        "event_type": event_type,
                        "message": message,
                        "reasoning": reasoning,
                        "metadata": metadata,
                        "severity": severity,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                },
                company_id=self.company_id
            )
        except ImportError:
            # WebSocket manager not available, skip broadcasting
            print(f"[Glass Door] WebSocket manager not available, event logged to database only")
        except Exception as e:
            # Don't fail on WebSocket errors
            print(f"[Glass Door] WebSocket broadcast failed: {e}")
