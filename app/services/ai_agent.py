"""Base AI Agent Framework for Autonomous Task Execution."""
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_task import AITask, AIToolExecution, AILearning
from app.services.ai_usage import AIUsageService


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

    def to_gemini_function(self):
        """Convert to Gemini function calling format."""
        return genai.protos.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    k: genai.protos.Schema(**v)
                    for k, v in self.parameters.items()
                },
                required=list(self.parameters.keys())
            )
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters."""
        try:
            result = await self.function(**kwargs)
            return {"status": "success", "result": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class BaseAIAgent(ABC):
    """
    Base class for all AI agents (Annie, Atlas, Alex).

    Provides core functionality for:
    - Task planning
    - Tool execution
    - Progress tracking
    - Error handling
    - Learning from feedback
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_usage_service = AIUsageService(db)

        # Configure AI model
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY not set")

        genai.configure(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

        # Tools available to this agent (set by subclasses)
        self.tools: List[AITool] = []

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Name of the agent (annie, atlas, alex)."""
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
You can autonomously complete tasks by planning steps and using available tools.
You have access to the following tools:

{tool_descriptions}

BEHAVIOR:
1. When given a task, break it down into clear steps
2. Execute each step using the appropriate tools
3. Handle errors gracefully and retry when possible
4. Provide clear progress updates
5. Report completion with a summary of what was accomplished

IMPORTANT RULES:
- Always use tools to interact with the system (don't just describe what you would do)
- Be proactive - if you see a problem, fix it
- Ask for clarification ONLY if task is truly ambiguous
- Provide specific, actionable results
- Log all important actions for audit trail

You are working for company: {{company_name}}
Current date: {datetime.utcnow().isoformat()}
"""

    async def execute_task(
        self,
        task: AITask,
        company_id: str,
        user_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Execute an AI task autonomously.

        Returns:
            (success: bool, error_message: Optional[str])
        """
        try:
            # Update task status
            task.status = "planning"
            task.started_at = datetime.utcnow()
            await self.db.commit()

            # Build the prompt for the AI
            system_prompt = self.build_system_prompt()
            user_prompt = f"""TASK: {task.task_description}

INPUT DATA:
{json.dumps(task.input_data, indent=2) if task.input_data else 'None'}

Please plan and execute this task step by step using the available tools.
For each step:
1. Describe what you're doing
2. Call the appropriate tool
3. Check the result
4. Proceed to next step or handle errors

When complete, summarize what was accomplished."""

            # Initialize Gemini with function calling
            model = genai.GenerativeModel(
                model_name=self.model_name,
                tools=[genai.protos.Tool(
                    function_declarations=[tool.to_gemini_function() for tool in self.tools]
                )],
                system_instruction=system_prompt
            )

            chat = model.start_chat()

            # Track execution
            task.status = "in_progress"
            task.planned_steps = []
            task.executed_steps = []
            total_tokens = 0

            # Send the task to the AI
            response = chat.send_message(user_prompt)

            # Process AI responses and function calls
            max_iterations = 20  # Prevent infinite loops
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                # Check if AI made function calls
                if response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        # Handle function calls
                        if hasattr(part, 'function_call') and part.function_call:
                            function_call = part.function_call
                            tool_name = function_call.name
                            tool_args = dict(function_call.args)

                            print(f"[{self.agent_name}] Calling tool: {tool_name}")
                            print(f"[{self.agent_name}] Arguments: {tool_args}")

                            # Find and execute the tool
                            tool = next((t for t in self.tools if t.name == tool_name), None)
                            if not tool:
                                error_msg = f"Tool {tool_name} not found"
                                print(f"[{self.agent_name}] ERROR: {error_msg}")
                                response = chat.send_message(
                                    genai.protos.Content(parts=[
                                        genai.protos.Part(
                                            function_response=genai.protos.FunctionResponse(
                                                name=tool_name,
                                                response={"error": error_msg}
                                            )
                                        )
                                    ])
                                )
                                continue

                            # Execute the tool
                            tool_start = datetime.utcnow()
                            tool_result = await tool.execute(**tool_args)
                            tool_duration = (datetime.utcnow() - tool_start).total_seconds() * 1000

                            # Log tool execution
                            tool_execution = AIToolExecution(
                                id=str(uuid.uuid4()),
                                task_id=task.id,
                                company_id=company_id,
                                tool_name=tool_name,
                                tool_category="api",  # TODO: categorize tools
                                input_parameters=tool_args,
                                output_result=tool_result,
                                status="success" if tool_result.get("status") == "success" else "failed",
                                error_message=tool_result.get("error"),
                                execution_time_ms=int(tool_duration),
                            )
                            self.db.add(tool_execution)

                            # Send tool result back to AI
                            response = chat.send_message(
                                genai.protos.Content(parts=[
                                    genai.protos.Part(
                                        function_response=genai.protos.FunctionResponse(
                                            name=tool_name,
                                            response=tool_result
                                        )
                                    )
                                ])
                            )

                            # Update task progress
                            task.progress_percent = min(95, (iteration / max_iterations) * 100)
                            await self.db.commit()

                        # Handle text responses (final answer or progress update)
                        elif hasattr(part, 'text') and part.text:
                            print(f"[{self.agent_name}] Response: {part.text}")

                            # Check if AI is done
                            if any(phrase in part.text.lower() for phrase in ['task complete', 'finished', 'done', 'summary:']):
                                task.status = "completed"
                                task.result = {"summary": part.text}
                                task.progress_percent = 100
                                task.completed_at = datetime.utcnow()

                                # Calculate execution time
                                if task.started_at:
                                    task.execution_time_seconds = int((task.completed_at - task.started_at).total_seconds())

                                # Log AI usage
                                await self.ai_usage_service.log_usage(
                                    company_id=company_id,
                                    user_id=user_id,
                                    operation_type="chat",  # Using chat quota for agent tasks
                                    status="success",
                                    tokens_used=total_tokens,
                                    cost_usd=0.0001,  # Approximate
                                )

                                await self.db.commit()
                                return (True, None)

                # If no more function calls and no completion signal, AI might be stuck
                if iteration >= max_iterations:
                    raise Exception("Max iterations reached - task may be too complex")

            # Should not reach here, but handle gracefully
            task.status = "failed"
            task.error_message = "Task did not complete within iteration limit"
            await self.db.commit()
            return (False, task.error_message)

        except Exception as e:
            error_msg = str(e)
            print(f"[{self.agent_name}] Task execution failed: {error_msg}")

            task.status = "failed"
            task.error_message = error_msg
            task.completed_at = datetime.utcnow()

            # Log failed usage
            await self.ai_usage_service.log_usage(
                company_id=company_id,
                user_id=user_id,
                operation_type="chat",
                status="failed",
                error_message=error_msg,
            )

            await self.db.commit()
            return (False, error_msg)
