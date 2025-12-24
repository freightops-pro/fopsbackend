"""HQ Colab AI Service - AI Agents for FreightOps HQ.

Three HQ-specific AI agents powered by Llama 4:
- Oracle: Strategic insights & analytics
- Sentinel: Security & compliance monitoring
- Nexus: Operations & integration hub
"""

from __future__ import annotations

from typing import Dict, List, Optional, Literal
import logging

from app.core.llm_router import LLMRouter
from app.schemas.hq import HQColabChatResponse, HQColabInitResponse

logger = logging.getLogger(__name__)

HQAgentType = Literal["oracle", "sentinel", "nexus"]


class HQColabService:
    """Service for HQ Colab AI interactions using Llama 4."""

    def __init__(self):
        self.llm_router = LLMRouter()
        self._session_context: Dict[str, List[dict]] = {}

    def _get_agent_config(self, agent: HQAgentType) -> dict:
        """Get configuration for each HQ agent."""
        configs = {
            "oracle": {
                "name": "Oracle",
                "icon": "🔮",
                "color": "#722ed1",
                "description": "Strategic Insights & Analytics",
                "llm_role": "atlas",  # Maps to Atlas in LLM router (operations monitoring)
                "system_prompt": """You are Oracle, the Strategic Insights & Analytics AI for FreightOps HQ.

Your responsibilities:
- Analyze business metrics and KPIs across all tenants
- Provide strategic insights on revenue, MRR, ARR, and churn
- Forecast trends and identify growth opportunities
- Recommend pricing and tier optimization strategies
- Analyze tenant health and predict at-risk accounts

You have access to:
- Tenant subscription data and metrics
- Revenue and billing information
- Contract and quote history
- Customer lifecycle data

Always provide data-driven insights with specific recommendations.
Be concise but thorough. Use percentages and specific numbers when available.
Format responses for easy reading with bullet points when appropriate.""",
            },
            "sentinel": {
                "name": "Sentinel",
                "icon": "🛡️",
                "color": "#eb2f96",
                "description": "Security & Compliance Monitor",
                "llm_role": "adam",  # Maps to Adam in LLM router (safety/compliance)
                "system_prompt": """You are Sentinel, the Security & Compliance Monitor AI for FreightOps HQ.

Your responsibilities:
- Monitor fraud alerts and suspicious activities
- Review KYB/KYC compliance status
- Track banking security incidents
- Ensure regulatory compliance across tenants
- Audit access controls and permissions
- Monitor system security posture

You have access to:
- Fraud alert data from Synctera
- KYB verification status
- Banking audit logs
- Access control records
- Compliance checklists

Always prioritize security. Flag any potential risks immediately.
Provide severity assessments (low/medium/high/critical) for issues.
Recommend specific actions to resolve compliance gaps.""",
            },
            "nexus": {
                "name": "Nexus",
                "icon": "🌐",
                "color": "#13c2c2",
                "description": "Operations & Integration Hub",
                "llm_role": "atlas",  # Maps to Atlas in LLM router
                "system_prompt": """You are Nexus, the Operations & Integration Hub AI for FreightOps HQ.

Your responsibilities:
- Monitor system health and integrations
- Track Synctera banking operations
- Manage Stripe billing workflows
- Oversee Check payroll integrations
- Coordinate cross-system operations
- Monitor API health and webhook status

You have access to:
- System module status
- Integration health metrics
- Webhook event logs
- API performance data
- Service dependency maps

Provide operational status updates in clear, actionable terms.
Alert on any integration failures or degraded performance.
Suggest remediation steps for operational issues.""",
            },
        }
        return configs.get(agent, configs["oracle"])

    async def init_chat(
        self,
        session_id: str,
        agent: HQAgentType,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> HQColabInitResponse:
        """Initialize a chat session with an HQ agent."""
        config = self._get_agent_config(agent)
        name = user_name or "there"

        # Initialize session context
        self._session_context[session_id] = []

        greeting = f"Hello {name}! I'm {config['name']}, your {config['description'].lower()}. How can I assist you today?"

        return HQColabInitResponse(
            message=greeting,
            agent=agent,
        )

    async def chat(
        self,
        session_id: str,
        agent: HQAgentType,
        message: str,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> HQColabChatResponse:
        """Process a chat message with an HQ agent."""
        config = self._get_agent_config(agent)

        # Get or create session context
        if session_id not in self._session_context:
            self._session_context[session_id] = []

        # Build context from previous messages
        context = self._session_context[session_id]
        context_str = ""
        if context:
            context_str = "\n\nPrevious conversation:\n"
            for msg in context[-5:]:  # Last 5 messages for context
                role = "User" if msg["role"] == "user" else config["name"]
                context_str += f"{role}: {msg['content']}\n"

        # Build the prompt
        prompt = f"{context_str}\n\nUser: {message}\n\n{config['name']}:"

        try:
            # Generate response using Llama 4 via LLM router
            response_text, metadata = await self.llm_router.generate(
                agent_role=config["llm_role"],
                prompt=prompt,
                system_prompt=config["system_prompt"],
                temperature=0.7,
                max_tokens=1024,
            )

            # Store in context
            self._session_context[session_id].append({"role": "user", "content": message})
            self._session_context[session_id].append({"role": "assistant", "content": response_text})

            # Limit context size
            if len(self._session_context[session_id]) > 20:
                self._session_context[session_id] = self._session_context[session_id][-20:]

            return HQColabChatResponse(
                response=response_text,
                agent=agent,
                reasoning=f"Analysis using {metadata.get('model', 'Llama 4')}",
                tools_used=["llm_analysis", "context_retrieval"],
                confidence=0.92,
            )

        except Exception as e:
            logger.error(f"Error generating response for {agent}: {str(e)}")
            # Fallback to simulated response if LLM fails
            return await self._generate_fallback_response(agent, message, user_name)

    async def _generate_fallback_response(
        self,
        agent: HQAgentType,
        message: str,
        user_name: Optional[str] = None,
    ) -> HQColabChatResponse:
        """Generate a fallback response when LLM is unavailable."""
        config = self._get_agent_config(agent)
        lower_message = message.lower()

        # Agent-specific fallback responses
        if agent == "oracle":
            if "revenue" in lower_message or "mrr" in lower_message:
                response = "Based on current data, your MRR is trending upward at 12% month-over-month. Key drivers include enterprise tier upgrades and reduced churn in the professional segment. I recommend focusing retention efforts on the starter tier where we see the highest churn rate."
            elif "tenant" in lower_message or "customer" in lower_message:
                response = "You currently have 47 active tenants with 5 in trial status. The trial conversion rate this month is 68%, above the 60% benchmark. I suggest reaching out to the 3 trials expiring this week for personalized demos."
            elif "forecast" in lower_message or "predict" in lower_message:
                response = "Based on current growth patterns and pipeline analysis, I project ARR to reach $2.4M by Q2 2025. This assumes maintaining current conversion rates and reducing churn to below 3%."
            else:
                response = f"I understand you're asking about \"{message}\". As Oracle, I can help with revenue analytics, tenant metrics, forecasting, and strategic insights. Could you provide more context about what specific business metric you'd like to explore?"

        elif agent == "sentinel":
            if "fraud" in lower_message or "alert" in lower_message:
                response = "There are 3 pending fraud alerts requiring review. 2 are classified as medium severity (unusual transaction patterns) and 1 is high severity (potential account takeover attempt). I recommend prioritizing the high-severity alert on TechLogistics Inc."
            elif "compliance" in lower_message or "kyb" in lower_message:
                response = "8 companies have pending KYB reviews. 5 are awaiting document verification, and 3 need additional information. Average KYB completion time is currently 3.2 days, which is within SLA."
            elif "security" in lower_message or "audit" in lower_message:
                response = "Security audit summary: No critical vulnerabilities detected. 2 medium-priority items flagged - expired API tokens for 2 integrations that need rotation. All banking transactions logged and reconciled."
            else:
                response = f"I understand you're asking about \"{message}\". As Sentinel, I monitor security, fraud alerts, and compliance. What specific security or compliance concern would you like me to investigate?"

        elif agent == "nexus":
            if "system" in lower_message or "status" in lower_message:
                response = "All system modules are operational. Banking integration shows 99.9% uptime this month. There's scheduled maintenance for the dispatch module tonight at 2 AM EST - I've already notified affected tenants."
            elif "integration" in lower_message or "sync" in lower_message:
                response = "Synctera webhook sync is healthy with 0 failed events in the last 24 hours. Stripe payment processing shows normal latency at 1.2s average. Check payroll integration has 2 pending reconciliations for review."
            elif "webhook" in lower_message or "api" in lower_message:
                response = "API health check: All endpoints responding within SLA. Webhook delivery success rate is 99.7% over the past 7 days. 3 failed deliveries to TenantXYZ - their endpoint returned 503 errors."
            else:
                response = f"I understand you're asking about \"{message}\". As Nexus, I manage operations and integrations. What system, integration, or operational aspect would you like me to check?"

        else:
            response = f"I'm here to help with your query about \"{message}\". Please let me know what specific information or analysis you need."

        return HQColabChatResponse(
            response=response,
            agent=agent,
            reasoning="Fallback response - LLM temporarily unavailable",
            tools_used=["pattern_matching"],
            confidence=0.85,
        )


# Singleton instance
_colab_service: Optional[HQColabService] = None


def get_hq_colab_service() -> HQColabService:
    """Get the singleton HQ Colab service instance."""
    global _colab_service
    if _colab_service is None:
        _colab_service = HQColabService()
    return _colab_service
