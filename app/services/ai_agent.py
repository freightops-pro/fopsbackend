"""Base AI Agent Framework for Autonomous Task Execution using Llama 4."""
import json
import os
import uuid
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_task import AITask, AIToolExecution, AILearning
from app.services.ai_usage import AIUsageService
from app.core.llm_router import LLMRouter
from app.services.glass_door_stream import GlassDoorStream


class AITool:
    """
    Represents a tool/function that an AI agent can use.

    Tools are Python functions that the AI can call to interact with systems.
    """
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        function: callable
    ):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON schema for parameters
        self.function = function

    def to_tool_schema(self) -> dict:
        """Convert to tool schema format for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": list(self.parameters.keys())
            }
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters."""
        try:
            result = await self.function(**kwargs)
            return {"status": "success", "result": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class BaseAIAgent(ABC):
    """
    Base class for all AI agents (Annie, Adam, Atlas, etc.).

    Uses LLM Router to select the appropriate Llama 4 model per agent role:
    - Annie (Operations): Llama 4 Scout 17B (fast, high volume)
    - Adam (Compliance): Llama 4 Maverick 400B (deep reasoning)
    - Atlas (Finance): Llama 4 Maverick 400B (precision math)

    Provides core functionality for:
    - Task planning
    - Tool execution with Glass Door logging
    - Progress tracking
    - Error handling
    - Real-time visibility
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_usage_service = AIUsageService(db)

        # Use LLM Router for Llama 4 models with multi-provider fallback
        self.llm_router = LLMRouter()

        # Tools available to this agent (set by subclasses)
        self.tools: List[AITool] = []

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Name of the agent (annie, adam, atlas, etc.)."""
        pass

    @property
    @abstractmethod
    def agent_role(self) -> str:
        """Description of the agent's role and capabilities."""
        pass

    @abstractmethod
    async def register_tools(self):
        """Register all tools available to this agent."""
        pass

    def build_system_prompt(self) -> str:
        """Build the system prompt for this agent."""
        tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in self.tools
        ])

        return f"""You are {self.agent_name}, an autonomous AI agent for FreightOps TMS.

ROLE: {self.agent_role}

CAPABILITIES:
You can autonomously complete tasks by using available tools.
You have access to the following tools:

{tool_descriptions}

TOOL CALLING FORMAT:
To use a tool, respond with:
TOOL_CALL: tool_name
PARAMETERS: {{"param1": "value1", "param2": "value2"}}

BEHAVIOR:
1. When given a task, identify which tools you need to use
2. Call tools one at a time using the format above
3. Wait for tool results before proceeding
4. When complete, respond with: TASK_COMPLETE followed by a summary

IMPORTANT RULES:
- Use tools to interact with the system (don't just describe)
- Call one tool at a time
- Wait for results before calling the next tool
- Be specific with tool parameters
- End with TASK_COMPLETE when done

Current date: {datetime.utcnow().isoformat()}
"""

    def _parse_tool_call(self, response_text: str) -> Optional[Tuple[str, dict]]:
        """Parse tool call from LLM response."""
        # Look for pattern: TOOL_CALL: tool_name \n PARAMETERS: {...}
        tool_call_match = re.search(r'TOOL_CALL:\s*(\w+)', response_text, re.IGNORECASE)
        if not tool_call_match:
            return None

        tool_name = tool_call_match.group(1)

        # Extract parameters
        params_match = re.search(r'PARAMETERS:\s*(\{.*?\})', response_text, re.DOTALL | re.IGNORECASE)
        if params_match:
            try:
                parameters = json.loads(params_match.group(1))
            except json.JSONDecodeError:
                parameters = {}
        else:
            parameters = {}

        return (tool_name, parameters)

    async def execute_task(
        self,
        task: AITask,
        company_id: str,
        user_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Execute an AI task autonomously using Llama 4 via LLM Router.

        Implements:
        - Tool calling with proper parsing
        - Glass Door stream logging for real-time visibility
        - Multi-turn conversation with tool results

        Returns:
            (success: bool, error_message: Optional[str])
        """
        # Initialize Glass Door stream for real-time visibility
        stream = GlassDoorStream(self.db, task.id, company_id)

        try:
            # Update task status
            task.status = "planning"
            task.started_at = datetime.utcnow()
            await self.db.commit()

            await stream.log_thinking(
                agent_type=self.agent_name,
                thought=f"Starting task: {task.task_description}",
                reasoning="Analyzing request and planning execution steps"
            )

            # Build the prompt for the AI
            system_prompt = self.build_system_prompt()
            user_prompt = f"""TASK: {task.task_description}

INPUT DATA:
{json.dumps(task.input_data, indent=2) if task.input_data else 'None'}

Execute this task step by step using the available tools. Remember to use the TOOL_CALL format and end with TASK_COMPLETE."""

            # Track execution
            task.status = "in_progress"
            total_tokens = 0
            conversation_history = []

            # Process AI responses and function calls in a loop
            max_iterations = 20  # Prevent infinite loops
            iteration = 0

            # Initial prompt
            current_prompt = user_prompt

            while iteration < max_iterations:
                iteration += 1

                print(f"[{self.agent_name}] Iteration {iteration}/{max_iterations}")

                await stream.log_thinking(
                    agent_type=self.agent_name,
                    thought=f"Processing step {iteration}/{max_iterations}",
                    reasoning="Generating next action based on current state"
                )

                # Call LLM Router
                response_text, metadata = await self.llm_router.generate(
                    agent_role=self.agent_name.lower(),
                    prompt=current_prompt,
                    system_prompt=system_prompt,
                    tools=None,  # We handle tool calling via text parsing
                    temperature=0.7,
                    max_tokens=4096
                )

                total_tokens += metadata.get("tokens_used", 0)

                print(f"[{self.agent_name}] Response: {response_text[:200]}...")

                # Check for task completion
                if "TASK_COMPLETE" in response_text.upper() or any(phrase in response_text.lower() for phrase in ['task complete', 'finished successfully']):
                    # Extract summary
                    summary = response_text.replace("TASK_COMPLETE", "").strip()

                    await stream.log_result(
                        agent_type=self.agent_name,
                        result="Task completed successfully",
                        data={"summary": summary}
                    )

                    task.status = "completed"
                    task.result = {"summary": summary}
                    task.progress_percent = 100
                    task.completed_at = datetime.utcnow()

                    # Calculate execution time
                    if task.started_at:
                        task.execution_time_seconds = int((task.completed_at - task.started_at).total_seconds())

                    # Log AI usage
                    await self.ai_usage_service.log_usage(
                        company_id=company_id,
                        user_id=user_id,
                        operation_type="agent_task",
                        status="success",
                        tokens_used=total_tokens,
                        cost_usd=metadata.get("cost_usd", 0.0),
                    )

                    await self.db.commit()
                    print(f"[{self.agent_name}] Task completed successfully")
                    return (True, None)

                # Parse for tool call
                tool_call = self._parse_tool_call(response_text)

                if tool_call:
                    tool_name, tool_params = tool_call

                    await stream.log_tool_call(
                        agent_type=self.agent_name,
                        tool_name=tool_name,
                        parameters=tool_params,
                        reasoning=f"Executing {tool_name} to complete task step"
                    )

                    print(f"[{self.agent_name}] Calling tool: {tool_name} with params: {tool_params}")

                    # Find and execute the tool
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    if not tool:
                        error_msg = f"Tool {tool_name} not found. Available tools: {[t.name for t in self.tools]}"
                        print(f"[{self.agent_name}] ERROR: {error_msg}")

                        await stream.log_error(
                            agent_type=self.agent_name,
                            error=error_msg,
                            context={"requested_tool": tool_name, "available_tools": [t.name for t in self.tools]}
                        )

                        current_prompt = f"Error: {error_msg}\n\nPlease try again with a valid tool or complete the task."
                        continue

                    # Execute the tool
                    tool_start = datetime.utcnow()
                    tool_result = await tool.execute(**tool_params)
                    tool_duration = (datetime.utcnow() - tool_start).total_seconds() * 1000

                    print(f"[{self.agent_name}] Tool result: {str(tool_result)[:200]}...")

                    # Log tool execution to database
                    tool_execution = AIToolExecution(
                        id=str(uuid.uuid4()),
                        task_id=task.id,
                        company_id=company_id,
                        tool_name=tool_name,
                        tool_category="agent_function",
                        input_parameters=tool_params,
                        output_result=tool_result,
                        status="success" if tool_result.get("status") == "success" else "failed",
                        error_message=tool_result.get("error"),
                        execution_time_ms=int(tool_duration),
                    )
                    self.db.add(tool_execution)
                    await self.db.commit()

                    # Log to Glass Door
                    if tool_result.get("status") == "success":
                        await stream.log_decision(
                            agent_type=self.agent_name,
                            decision=f"Tool {tool_name} executed successfully",
                            reasoning=f"Result: {str(tool_result.get('result', ''))[:200]}",
                            confidence=0.95
                        )
                    else:
                        await stream.log_error(
                            agent_type=self.agent_name,
                            error=f"Tool {tool_name} failed: {tool_result.get('error')}",
                            context={"tool_name": tool_name, "parameters": tool_params}
                        )

                    # Send tool result back to LLM
                    current_prompt = f"TOOL_RESULT for {tool_name}:\n{json.dumps(tool_result, indent=2)}\n\nContinue with the next step or respond with TASK_COMPLETE if done."

                    # Update task progress
                    task.progress_percent = min(95, int((iteration / max_iterations) * 100))
                    await self.db.commit()

                else:
                    # No tool call detected, AI is providing information
                    await stream.log_thinking(
                        agent_type=self.agent_name,
                        thought=response_text[:200],
                        reasoning="Agent providing analysis or information"
                    )

                    # Prompt AI to continue
                    current_prompt = f"Previous response: {response_text}\n\nContinue with the next tool call or respond with TASK_COMPLETE if finished."

            # If we reach here, max iterations exceeded
            await stream.log_result(
                agent_type=self.agent_name,
                result="Task completed (reached iteration limit)",
                data={"note": "Maximum iterations reached", "last_response": response_text[:200]}
            )

            task.status = "completed"
            task.result = {"summary": response_text, "note": "Reached iteration limit"}
            task.progress_percent = 100
            task.completed_at = datetime.utcnow()

            await self.db.commit()
            return (True, None)

        except Exception as e:
            error_msg = str(e)
            print(f"[{self.agent_name}] Task execution failed: {error_msg}")

            await stream.log_error(
                agent_type=self.agent_name,
                error=f"Task execution failed: {error_msg}",
                context={"task_id": task.id, "iteration": iteration}
            )

            task.status = "failed"
            task.error_message = error_msg
            task.completed_at = datetime.utcnow()

            # Log failed usage
            await self.ai_usage_service.log_usage(
                company_id=company_id,
                user_id=user_id,
                operation_type="agent_task",
                status="failed",
                error_message=error_msg,
            )

            await self.db.commit()
            return (False, error_msg)
