"""
AI Agent Processor with LLM integration and tool capabilities.

This module handles the actual AI processing using Grok (Llama 4) API
with tool use for internet research, document creation, and database queries.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.hq_ai_task import (
    HQAITask,
    HQAITaskEvent,
    HQAITaskEventType,
    HQAIAgentType,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================================
# Agent System Prompts
# ============================================================================

ORACLE_SYSTEM_PROMPT = """You are Oracle, the Strategic Insights AI Agent for FreightOps HQ.

Your role is to analyze business metrics, forecast trends, and identify growth opportunities for the freight transportation management platform.

## Your Capabilities:
- Analyze MRR (Monthly Recurring Revenue) trends
- Identify at-risk tenants based on usage patterns
- Forecast revenue growth
- Analyze customer segments and cohorts
- Provide data-driven business recommendations

## Your Personality:
- Analytical and data-driven
- Strategic and forward-thinking
- Clear and actionable in recommendations

## Available Tools:
- web_search: Search the internet for market research and industry data
- query_database: Query tenant metrics, revenue data, and usage statistics
- create_report: Generate formatted reports and documents

When given a task, break it down into steps, use your tools to gather data, and provide actionable insights.
"""

SENTINEL_SYSTEM_PROMPT = """You are Sentinel, the Security & Compliance AI Agent for FreightOps HQ.

Your role is to monitor fraud alerts, ensure KYB/KYC compliance, and detect security incidents across the platform.

## Your Capabilities:
- Review and analyze fraud alerts
- Verify KYB/KYC compliance status
- Detect suspicious activity patterns
- Generate compliance reports
- Monitor security incidents

## Your Personality:
- Vigilant and thorough
- Risk-aware and cautious
- Clear about security implications

## Available Tools:
- web_search: Research compliance requirements and fraud patterns
- query_database: Access fraud alerts, compliance records, and audit logs
- create_report: Generate compliance and security reports

When given a task, methodically check all relevant data sources and provide comprehensive security assessments.
"""

NEXUS_SYSTEM_PROMPT = """You are Nexus, the Operations Hub AI Agent for FreightOps HQ.

Your role is to manage system health, monitor integrations, and optimize cross-system operations.

## Your Capabilities:
- Monitor system health and uptime
- Check integration status (Samsara, Motive, Gusto, etc.)
- Analyze API error rates and performance
- Troubleshoot operational issues
- Coordinate cross-system workflows

## Your Personality:
- Technical and precise
- Proactive about system health
- Clear about operational impacts

## Available Tools:
- web_search: Research technical solutions and integration documentation
- query_database: Access system logs, integration status, and metrics
- create_report: Generate operational reports and status updates

When given a task, provide comprehensive operational assessments with clear action items.
"""

SUPPORT_AGENT_SYSTEM_PROMPT = """You are a Support AI Agent for FreightOps, a transportation management platform.

Your role is to help tenant users with their questions about the platform, troubleshoot issues, and provide guidance on using FreightOps features.

## Platform Features You Support:
- Dispatch & Load Management (creating loads, tracking shipments)
- Fleet Management (equipment, drivers, compliance)
- Fuel & IFTA tracking (fuel cards, jurisdiction reporting)
- Accounting & Billing (invoices, settlements, factoring)
- Driver Management (onboarding, CDL tracking, payroll)
- Banking & Payments (cards, transfers, reconciliation)

## Your Capabilities:
- Answer questions about platform features
- Guide users through workflows
- Troubleshoot common issues
- Explain DOT compliance requirements
- Help with IFTA reporting questions

## Your Personality:
- Helpful and patient
- Clear and concise
- Knowledgeable about freight industry

## Available Tools:
- web_search: Research DOT regulations, IFTA rules, and industry standards
- query_documentation: Access platform documentation and help articles
- create_ticket: Escalate complex issues to human support

Always be helpful and provide actionable guidance. If you don't know something, offer to escalate to human support.
"""


# ============================================================================
# Tools Definition (OpenAI-compatible format for Grok)
# ============================================================================

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for information. Use this for market research, compliance requirements, technical documentation, or industry data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Query the FreightOps database for metrics, records, and analytics. Returns JSON data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": [
                            "tenant_metrics",
                            "revenue_data",
                            "fraud_alerts",
                            "compliance_records",
                            "system_health",
                            "integration_status",
                            "usage_stats"
                        ],
                        "description": "The type of data to query"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional filters for the query (e.g., date_range, tenant_id)"
                    }
                },
                "required": ["query_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_report",
            "description": "Create a formatted report or document. Returns the report content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Report title"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "html", "text"],
                        "description": "Output format",
                        "default": "markdown"
                    },
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "content": {"type": "string"}
                            }
                        },
                        "description": "Report sections"
                    }
                },
                "required": ["title", "sections"]
            }
        }
    }
]


# ============================================================================
# Tool Implementations
# ============================================================================

async def execute_web_search(query: str, num_results: int = 5) -> Dict[str, Any]:
    """
    Execute a web search using Grok's built-in search or external API.
    """
    logger.info(f"Web search: {query}")

    # Check if we have a search API key (Tavily, SerpAPI, etc.)
    tavily_key = getattr(settings, 'tavily_api_key', None)

    if tavily_key:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": tavily_key,
                        "query": query,
                        "max_results": num_results,
                        "include_answer": True
                    },
                    timeout=30.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "query": query,
                        "answer": data.get("answer", ""),
                        "results": [
                            {
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "snippet": r.get("content", "")[:500]
                            }
                            for r in data.get("results", [])[:num_results]
                        ]
                    }
        except Exception as e:
            logger.error(f"Tavily search error: {e}")

    # Fallback placeholder response
    return {
        "success": True,
        "query": query,
        "results": [
            {
                "title": f"Search result for: {query}",
                "url": "https://example.com/result",
                "snippet": "Web search API not configured. Set TAVILY_API_KEY for real search results."
            }
        ],
        "note": "Connect Tavily API for real web search results."
    }


async def execute_database_query(
    db: AsyncSession,
    query_type: str,
    filters: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Execute a database query based on the query type.
    """
    logger.info(f"Database query: {query_type} with filters {filters}")

    # TODO: Implement actual database queries
    # For now, return placeholder data

    if query_type == "tenant_metrics":
        return {
            "total_tenants": 150,
            "active_tenants": 142,
            "churned_this_month": 2,
            "new_this_month": 8,
            "avg_mrr": 599
        }
    elif query_type == "revenue_data":
        return {
            "current_mrr": 89850,
            "previous_mrr": 85000,
            "growth_rate": 5.7,
            "arr": 1078200
        }
    elif query_type == "fraud_alerts":
        return {
            "open_alerts": 3,
            "resolved_this_week": 12,
            "high_severity": 1,
            "medium_severity": 2
        }
    elif query_type == "compliance_records":
        return {
            "pending_kyb": 5,
            "approved_this_week": 15,
            "rejected_this_week": 2,
            "compliance_rate": 0.92
        }
    elif query_type == "system_health":
        return {
            "uptime_percent": 99.95,
            "avg_response_time_ms": 145,
            "error_rate": 0.02,
            "active_connections": 234
        }
    elif query_type == "integration_status":
        return {
            "samsara": {"status": "healthy", "last_sync": "2 min ago"},
            "motive": {"status": "healthy", "last_sync": "5 min ago"},
            "gusto": {"status": "healthy", "last_sync": "1 hour ago"},
            "quickbooks": {"status": "degraded", "error": "Rate limited"}
        }
    else:
        return {"error": f"Unknown query type: {query_type}"}


async def execute_create_report(
    title: str,
    sections: List[Dict],
    format: str = "markdown"
) -> Dict[str, Any]:
    """
    Create a formatted report document.
    """
    logger.info(f"Creating report: {title}")

    if format == "markdown":
        content = f"# {title}\n\n"
        content += f"*Generated: {datetime.utcnow().isoformat()}*\n\n"
        for section in sections:
            content += f"## {section.get('heading', 'Section')}\n\n"
            content += f"{section.get('content', '')}\n\n"
    else:
        content = f"{title}\n\n"
        for section in sections:
            content += f"{section.get('heading', 'Section')}\n"
            content += f"{section.get('content', '')}\n\n"

    return {
        "success": True,
        "title": title,
        "format": format,
        "content": content
    }


# ============================================================================
# Main Agent Processor
# ============================================================================

class AIAgentProcessor:
    """Processes AI tasks using Grok (Llama 4) API with tool use."""

    def __init__(self):
        # Grok API configuration
        self.grok_api_key = getattr(settings, 'grok_api_key', None) or getattr(settings, 'xai_api_key', None)
        self.grok_base_url = getattr(settings, 'grok_base_url', "https://api.x.ai/v1")
        self.grok_model = getattr(settings, 'grok_model', "grok-3")  # or "llama-4" depending on endpoint

    def get_system_prompt(self, agent_type: HQAIAgentType) -> str:
        """Get the system prompt for the given agent type."""
        prompts = {
            HQAIAgentType.ORACLE: ORACLE_SYSTEM_PROMPT,
            HQAIAgentType.SENTINEL: SENTINEL_SYSTEM_PROMPT,
            HQAIAgentType.NEXUS: NEXUS_SYSTEM_PROMPT,
        }
        return prompts.get(agent_type, ORACLE_SYSTEM_PROMPT)

    async def process(
        self,
        db: AsyncSession,
        task: HQAITask,
        add_event_callback
    ) -> str:
        """
        Process a task using Grok API.

        Args:
            db: Database session
            task: The task to process
            add_event_callback: Callback to add events to the task

        Returns:
            The final result string
        """
        system_prompt = self.get_system_prompt(task.agent_type)

        if not self.grok_api_key:
            logger.warning("No Grok API key configured, using mock response")
            return await self._mock_process(db, task, add_event_callback)

        return await self._process_with_grok(
            db, task, system_prompt, add_event_callback
        )

    async def _mock_process(
        self,
        db: AsyncSession,
        task: HQAITask,
        add_event_callback
    ) -> str:
        """Mock processing when no API key is configured."""
        await add_event_callback(
            db, task.id, HQAITaskEventType.THINKING,
            "Analyzing request (mock mode - no API key configured)..."
        )

        import asyncio
        await asyncio.sleep(2)

        await add_event_callback(
            db, task.id, HQAITaskEventType.ACTION,
            "Gathering relevant data..."
        )

        await asyncio.sleep(2)

        result = f"""## Task Analysis

**Task:** {task.description}

**Agent:** {task.agent_type.value.title()}

---

### Mock Response

This is a placeholder response because no Grok API key is configured.

To enable full AI agent capabilities:

1. **Set Grok API Key:**
   - Set `GROK_API_KEY` or `XAI_API_KEY` in your environment

2. **Optional - Web Search:**
   - Set `TAVILY_API_KEY` for internet research capabilities

The agent will then be able to:
- Search the web for research
- Query the database for metrics
- Generate comprehensive reports
- Provide actionable insights

---

*Generated at {datetime.utcnow().isoformat()}*
"""
        return result

    async def _process_with_grok(
        self,
        db: AsyncSession,
        task: HQAITask,
        system_prompt: str,
        add_event_callback
    ) -> str:
        """Process using Grok API (OpenAI-compatible) with tool use."""
        async with httpx.AsyncClient() as client:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task.description}
            ]

            # Initial API call
            response = await client.post(
                f"{self.grok_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.grok_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.grok_model,
                    "messages": messages,
                    "tools": AGENT_TOOLS,
                    "tool_choice": "auto",
                    "max_tokens": 4096,
                    "temperature": 0.7
                },
                timeout=120.0
            )

            if response.status_code != 200:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return f"API Error: {response.status_code} - {response.text[:200]}"

            result = response.json()
            message = result.get("choices", [{}])[0].get("message", {})

            # Handle tool use loop
            max_iterations = 10
            iteration = 0

            while message.get("tool_calls") and iteration < max_iterations:
                iteration += 1

                # Add assistant message with tool calls
                messages.append(message)

                # Process each tool call
                for tool_call in message.get("tool_calls", []):
                    function = tool_call.get("function", {})
                    tool_name = function.get("name")
                    tool_args = json.loads(function.get("arguments", "{}"))
                    tool_id = tool_call.get("id")

                    await add_event_callback(
                        db, task.id, HQAITaskEventType.ACTION,
                        f"Using tool: {tool_name}"
                    )

                    # Execute the tool
                    tool_result = await self._execute_tool(db, tool_name, tool_args)

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": json.dumps(tool_result)
                    })

                # Continue conversation with tool results
                response = await client.post(
                    f"{self.grok_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.grok_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.grok_model,
                        "messages": messages,
                        "tools": AGENT_TOOLS,
                        "tool_choice": "auto",
                        "max_tokens": 4096,
                        "temperature": 0.7
                    },
                    timeout=120.0
                )

                if response.status_code != 200:
                    logger.error(f"Grok API error: {response.status_code} - {response.text}")
                    break

                result = response.json()
                message = result.get("choices", [{}])[0].get("message", {})

            # Extract final text response
            final_text = message.get("content", "")

            return final_text or "No response generated"

    async def _execute_tool(
        self,
        db: AsyncSession,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        if tool_name == "web_search":
            return await execute_web_search(
                tool_input.get("query", ""),
                tool_input.get("num_results", 5)
            )
        elif tool_name == "query_database":
            return await execute_database_query(
                db,
                tool_input.get("query_type", ""),
                tool_input.get("filters")
            )
        elif tool_name == "create_report":
            return await execute_create_report(
                tool_input.get("title", "Report"),
                tool_input.get("sections", []),
                tool_input.get("format", "markdown")
            )
        else:
            return {"error": f"Unknown tool: {tool_name}"}


# Singleton processor instance
_processor: Optional[AIAgentProcessor] = None


def get_processor() -> AIAgentProcessor:
    """Get the singleton processor instance."""
    global _processor
    if _processor is None:
        _processor = AIAgentProcessor()
    return _processor
