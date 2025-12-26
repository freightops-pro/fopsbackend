"""
LLM Model Router - Llama 4 Native Architecture for AI Employees.

FIVE AI EMPLOYEES:
- Annie (Dispatcher): Llama 4 Scout 17B (500 loads/month capacity)
- Adam (Safety/Compliance Officer): Llama 4 Maverick 400B (safety-critical reasoning)
- Felix (Fleet Manager): Llama 4 Maverick 400B (fleet ops decisions)
- Harper (HR/Payroll): Llama 4 Maverick 400B (payroll calculations)
- Atlas (Supervisor): Llama 4 Scout 17B (operations monitoring)

Infrastructure Model:
- Scout 17B: High-throughput operations
- Maverick 400B: Deep reasoning and precision tasks
- <500ms inter-agent communication under load
- Self-hosted = zero API costs, <2s response times, data sovereignty

Provider Hierarchy:
1. Self-hosted (production) → vLLM/TGI on NVIDIA GPUs
2. Groq (testing/demo) → Fast inference, free tier
3. AWS Bedrock (fallback) → Enterprise reliability
"""

import os
import asyncio
from typing import Literal, Optional
import json


AgentRole = Literal["annie", "adam", "felix", "fleet_manager", "cfo_analyst", "harper", "atlas", "alex"]


class LLMRouter:
    """
    Routes AI requests to the optimal Llama 4 model per agent.

    Supports multi-provider fallback for reliability.
    """

    def __init__(self):
        # Provider 1: Self-hosted (future)
        self.self_hosted_endpoint = os.getenv("SELF_HOSTED_LLM_ENDPOINT")

        # Provider 2: Groq (primary)
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq = None
        if self.groq_api_key:
            try:
                from groq import AsyncGroq
                self.groq = AsyncGroq(api_key=self.groq_api_key)
            except ImportError:
                print("[LLM Router] Warning: groq package not installed. Install with: pip install groq")

        # Provider 3: AWS Bedrock (fallback)
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.bedrock = None
        if os.getenv("AWS_ACCESS_KEY_ID"):
            try:
                import boto3
                self.bedrock = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=self.aws_region,
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
                )
            except ImportError:
                print("[LLM Router] Warning: boto3 not installed. Install with: pip install boto3")

    def get_model_config(self, agent_role: AgentRole) -> dict:
        """
        Returns Llama 4 model configuration for the agent.

        Returns:
            {
                "model_id": "llama-4-scout-17b-instruct" | "llama-4-maverick-400b-instruct",
                "groq_model": "llama-4-scout-17b-instruct",
                "bedrock_model": "meta.llama-4-scout-17b-instruct-v1:0",
                "context_window": int,
                "cost_per_1m_tokens": float,
                "capabilities": list,
                "reasoning": str
            }
        """
        if agent_role == "annie":
            # Annie - Dispatcher (High-throughput operations)
            # Target capacity: 500 loads/month
            # Uses Llama 4 Scout with VISION for document OCR
            return {
                "model_id": "llama-4-scout-17b-instruct",
                "groq_model": "llama-3.1-70b-versatile",  # Text-only tasks
                "groq_vision_model": "meta-llama/llama-4-scout-17b-16e-instruct",  # Vision/OCR tasks
                "bedrock_model": "meta.llama-4-scout-17b-instruct-v1:0",
                "self_hosted_model": "meta-llama/Llama-4-Scout-17B-Instruct",
                "context_window": 128_000,  # 128K token context
                "cost_per_1m_tokens": 0.10,
                "capabilities": ["vision", "ocr", "fast_inference", "load_management"],
                "employee_role": "AI Dispatcher",
                "monthly_capacity": "500 loads",
                "reasoning": "Scout 17B with vision for dispatch: driver matching, load assignment, document OCR"
            }

        elif agent_role == "adam":
            # Adam - Safety/Compliance Officer (Safety-critical reasoning)
            return {
                "model_id": "llama-4-maverick-400b-instruct",
                "groq_model": "llama-3.1-70b-versatile",  # Groq fallback
                "bedrock_model": "meta.llama-4-maverick-400b-instruct-v1:0",
                "self_hosted_model": "meta-llama/Llama-4-Maverick-400B-Instruct",
                "context_window": 128_000,
                "cost_per_1m_tokens": 2.50,
                "capabilities": ["deep_reasoning", "MoE", "compliance_expertise", "safety_critical", "DOT_regulations"],
                "employee_role": "AI Safety/Compliance Officer",
                "monthly_capacity": "Unlimited reviews",
                "reasoning": "Maverick 400B (MoE) for safety-critical compliance: DOT audits, HOS validation, CFR citations"
            }

        elif agent_role in ("felix", "fleet_manager"):
            # Felix / Fleet Manager (Fleet operations decisions)
            return {
                "model_id": "llama-4-maverick-400b-instruct",
                "groq_model": "llama-3.1-70b-versatile",
                "bedrock_model": "meta.llama-4-maverick-400b-instruct-v1:0",
                "self_hosted_model": "meta-llama/Llama-4-Maverick-400B-Instruct",
                "context_window": 128_000,
                "cost_per_1m_tokens": 2.50,
                "capabilities": ["deep_reasoning", "MoE", "fleet_optimization", "maintenance_planning", "route_planning"],
                "employee_role": "AI Fleet Manager (Felix)",
                "monthly_capacity": "50-500 trucks",
                "reasoning": "Maverick 400B (MoE) for fleet decisions: maintenance schedules, fuel optimization, route planning"
            }

        elif agent_role == "cfo_analyst":
            # CFO Analyst (Financial analysis)
            return {
                "model_id": "llama-4-maverick-400b-instruct",
                "groq_model": "llama-3.1-70b-versatile",
                "bedrock_model": "meta.llama-4-maverick-400b-instruct-v1:0",
                "self_hosted_model": "meta-llama/Llama-4-Maverick-400B-Instruct",
                "context_window": 128_000,
                "cost_per_1m_tokens": 2.50,
                "capabilities": ["deep_reasoning", "MoE", "financial_analysis", "precision_math", "margin_optimization"],
                "employee_role": "AI CFO Analyst",
                "monthly_capacity": "500+ loads",
                "reasoning": "Maverick 400B (MoE) for financial analysis: margin calculation, rate optimization, P&L reporting"
            }

        elif agent_role == "harper":
            # Harper - HR & Payroll Specialist (Precision payroll calculations)
            return {
                "model_id": "llama-4-maverick-400b-instruct",
                "groq_model": "llama-3.1-70b-versatile",
                "bedrock_model": "meta.llama-4-maverick-400b-instruct-v1:0",
                "self_hosted_model": "meta-llama/Llama-4-Maverick-400B-Instruct",
                "context_window": 128_000,
                "cost_per_1m_tokens": 2.50,
                "capabilities": ["deep_reasoning", "MoE", "precision_math", "payroll_compliance", "tax_calculations"],
                "employee_role": "AI HR & Payroll Specialist",
                "monthly_capacity": "Unlimited capacity",
                "reasoning": "Maverick 400B (MoE) for payroll: driver settlements, tax calculations, CheckHQ integration"
            }

        elif agent_role == "atlas":
            # Atlas - Monitoring and Exception Management (Operations oversight)
            return {
                "model_id": "llama-4-scout-17b-instruct",
                "groq_model": "llama-3.1-70b-versatile",  # Groq fallback
                "bedrock_model": "meta.llama-4-scout-17b-instruct-v1:0",
                "self_hosted_model": "meta-llama/Llama-4-Scout-17B-Instruct",
                "context_window": 10_000_000,  # 10M token context
                "cost_per_1m_tokens": 0.10,
                "capabilities": ["monitoring", "exception_detection", "performance_analysis", "alerting"],
                "employee_role": "AI Operations Monitor",
                "monthly_capacity": "24/7 monitoring",
                "reasoning": "Scout 17B for continuous monitoring: exception detection, load tracking, proactive alerting"
            }

        elif agent_role == "alex":
            # Alex - Sales and Analytics (Business intelligence)
            return {
                "model_id": "llama-4-scout-17b-instruct",
                "groq_model": "llama-3.1-70b-versatile",  # Groq fallback
                "bedrock_model": "meta.llama-4-scout-17b-instruct-v1:0",
                "self_hosted_model": "meta-llama/Llama-4-Scout-17B-Instruct",
                "context_window": 10_000_000,  # 10M token context
                "cost_per_1m_tokens": 0.10,
                "capabilities": ["analytics", "forecasting", "churn_prediction", "business_intelligence"],
                "employee_role": "AI Sales and Analytics",
                "monthly_capacity": "Unlimited insights",
                "reasoning": "Scout 17B for analytics: revenue forecasting, churn prediction, KPI aggregation"
            }

        elif agent_role == "scout":
            # Scout - Lead enrichment and FMCSA data processing
            return {
                "model_id": "llama-4-scout-17b-instruct",
                "groq_model": "llama-3.1-70b-versatile",  # Groq fallback
                "bedrock_model": "meta.llama-4-scout-17b-instruct-v1:0",
                "self_hosted_model": "meta-llama/Llama-4-Scout-17B-Instruct",
                "context_window": 128_000,
                "cost_per_1m_tokens": 0.10,
                "capabilities": ["lead_enrichment", "fmcsa_processing", "data_extraction", "outreach_generation"],
                "employee_role": "AI Lead Scout",
                "monthly_capacity": "Unlimited leads",
                "reasoning": "Scout 17B for lead processing: FMCSA data enrichment, contact extraction, outreach templates"
            }

        else:
            raise ValueError(f"Unknown agent role: {agent_role}")

    async def generate(
        self,
        agent_role: AgentRole,
        prompt: str,
        system_prompt: str = None,
        tools: list = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        image_data: str = None
    ) -> tuple[str, dict]:
        """
        Generate response using Llama 4 with multi-provider fallback.

        Tries providers in order:
        1. Self-hosted (if configured)
        2. Groq (primary - fast and free)
        3. AWS Bedrock (fallback - reliable)

        Args:
            image_data: Optional base64-encoded image for vision (Annie/Scout only)

        Returns:
            (response_text, metadata)
        """
        config = self.get_model_config(agent_role)

        # Try self-hosted first (future)
        if self.self_hosted_endpoint:
            try:
                return await self._generate_self_hosted(
                    prompt, system_prompt, tools, config, temperature, max_tokens
                )
            except Exception as e:
                print(f"[LLM Router] Self-hosted failed: {e}, falling back to Groq")

        # Try Groq (primary)
        if self.groq:
            try:
                return await self._generate_groq(
                    prompt, system_prompt, tools, config, temperature, max_tokens, image_data
                )
            except Exception as e:
                print(f"[LLM Router] Groq failed: {e}, falling back to Bedrock")

        # Try AWS Bedrock (fallback)
        if self.bedrock:
            try:
                return await self._generate_bedrock(
                    prompt, system_prompt, tools, config, temperature, max_tokens
                )
            except Exception as e:
                print(f"[LLM Router] Bedrock failed: {e}")
                raise Exception("All LLM providers failed")

        raise Exception("No LLM providers configured. Set GROQ_API_KEY or AWS credentials.")

    async def _generate_groq(
        self,
        prompt: str,
        system_prompt: str,
        tools: list,
        config: dict,
        temperature: float,
        max_tokens: int,
        image_data: str = None
    ) -> tuple[str, dict]:
        """Generate using Groq (fast Llama 4 inference).

        Args:
            image_data: Optional base64-encoded image for vision tasks.
                        Format: "data:image/jpeg;base64,..." or just the base64 string
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Handle vision (image) input
        if image_data:
            # Use vision model for image tasks
            model = config.get("groq_vision_model", config["groq_model"])

            # Build multimodal content
            content = [
                {"type": "text", "text": prompt}
            ]

            # Format image data properly
            if image_data.startswith("data:"):
                image_url = image_data
            else:
                # Assume JPEG if no prefix
                image_url = f"data:image/jpeg;base64,{image_data}"

            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

            messages.append({"role": "user", "content": content})
        else:
            # Text-only request
            model = config["groq_model"]
            messages.append({"role": "user", "content": prompt})

        completion = await self.groq.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            # tools=tools if tools else None  # TODO: Add when Groq supports function calling
        )

        return completion.choices[0].message.content, {
            "model": model,
            "provider": "groq",
            "tokens_used": completion.usage.total_tokens,
            "input_tokens": completion.usage.prompt_tokens,
            "output_tokens": completion.usage.completion_tokens,
            "cost_usd": (completion.usage.total_tokens / 1_000_000) * config["cost_per_1m_tokens"],
            "vision_used": image_data is not None
        }

    async def _generate_bedrock(
        self,
        prompt: str,
        system_prompt: str,
        tools: list,
        config: dict,
        temperature: float,
        max_tokens: int
    ) -> tuple[str, dict]:
        """Generate using AWS Bedrock (reliable fallback)."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        request_body = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            request_body["tools"] = tools

        response = self.bedrock.invoke_model(
            modelId=config["bedrock_model"],
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())
        content = response_body['content'][0]['text']

        # Estimate tokens (Bedrock doesn't always return usage)
        estimated_tokens = len(prompt.split()) + len(content.split()) * 1.3

        return content, {
            "model": config["model_id"],
            "provider": "aws_bedrock",
            "tokens_used": int(estimated_tokens),
            "cost_usd": (estimated_tokens / 1_000_000) * config["cost_per_1m_tokens"]
        }

    async def _generate_self_hosted(
        self,
        prompt: str,
        system_prompt: str,
        tools: list,
        config: dict,
        temperature: float,
        max_tokens: int
    ) -> tuple[str, dict]:
        """
        Generate using self-hosted Llama 4 (future implementation).

        Will use vLLM or TGI on dedicated GPUs.
        """
        import aiohttp

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.self_hosted_endpoint}/v1/chat/completions",
                json={
                    "model": config["self_hosted_model"],
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "tools": tools if tools else None
                }
            ) as response:
                data = await response.json()

                return data["choices"][0]["message"]["content"], {
                    "model": config["model_id"],
                    "provider": "self_hosted",
                    "tokens_used": data["usage"]["total_tokens"],
                    "cost_usd": 0.0  # Free when self-hosted
                }
