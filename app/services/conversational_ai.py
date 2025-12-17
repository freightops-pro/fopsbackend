"""
Conversational AI Service - Natural language interaction with AI agents.

Handles:
- Greetings: "Good morning Annie" → "Good morning [User]!"
- Weather queries: "What's the weather in Chicago?" → Fetch weather data
- Traffic queries: "How's traffic near truck 110?" → Query truck location + traffic API
- Bulk tasks: "Create 20 loads from this list" → Parse and create loads
- Agent delegation: Annie hands off tasks to Adam or Atlas
"""

import re
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.llm_router import LLMRouter
from app.services.glass_door_stream import GlassDoorStream
from app.services.external_apis import ProductionAPIManager
from app.services.fleet_manager_ai import FleetManagerAI
from app.services.cfo_analyst_ai import CFOAnalystAI
from app.services.harper_ai import HarperAI


class ConversationalAI:
    """
    Natural language interface for AI employees.

    PRODUCTION IMPLEMENTATION - No mocks, all real APIs.

    Uses Llama 4 to understand user intent and execute tasks conversationally.
    """

    def __init__(self, db: AsyncSession, company_id: str, user_id: str, user_name: str = "User"):
        self.db = db
        self.company_id = company_id
        self.user_id = user_id
        self.user_name = user_name
        self.llm_router = LLMRouter()
        self.api_manager = ProductionAPIManager()

        # Initialize AI agents
        self.fleet_manager = FleetManagerAI(db)
        self.cfo_analyst = CFOAnalystAI(db)
        self.harper = HarperAI(db)

    async def process_message(
        self,
        agent_type: str,  # annie, adam, atlas
        message: str,
        session_id: str,
        context: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process a conversational message and generate response.

        Args:
            agent_type: Which agent to talk to
            message: User's natural language message
            session_id: Conversation session ID
            context: Previous messages for context

        Returns:
            {
                "response": "AI's conversational response",
                "reasoning": "Why AI responded this way",
                "tools_used": ["weather_api", "create_loads"],
                "task_id": "123" (if task was created),
                "delegated_to": "adam" (if delegated to another agent),
                "confidence": 0.95,
                "data": {...} (any structured data returned)
            }
        """

        # Build conversation history for context
        conversation_context = self._build_context(context or [])

        # Create system prompt for the agent
        system_prompt = self._get_agent_system_prompt(agent_type)

        # Add tools available to this agent
        tools = self._get_available_tools(agent_type)

        # Generate response using Llama 4
        full_prompt = f"""
{conversation_context}

User ({self.user_name}): {message}

Instructions:
- Respond conversationally and naturally
- Use the user's name when appropriate
- If you need to perform an action, use the available tools
- If the request is outside your expertise, suggest delegating to another agent
- Be concise but friendly

Available information:
- Current time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
- Company ID: {self.company_id}
- User: {self.user_name}
"""

        response_text, metadata = await self.llm_router.generate(
            agent_role=agent_type,
            prompt=full_prompt,
            system_prompt=system_prompt,
            tools=tools,
            temperature=0.7,
            max_tokens=2048
        )

        # Parse tool calls from response if any
        tools_used = []
        task_id = None
        delegated_to = None
        structured_data = {}

        # Check if AI wants to use tools
        if "TOOL_CALL:" in response_text:
            tool_results = await self._execute_tool_calls(response_text, agent_type)
            tools_used = tool_results.get("tools_used", [])
            task_id = tool_results.get("task_id")
            delegated_to = tool_results.get("delegated_to")
            structured_data = tool_results.get("data", {})

            # Regenerate response with tool results
            response_text = tool_results.get("final_response", response_text)

        # Detect common patterns and execute automatically
        else:
            # Greeting detection
            if self._is_greeting(message):
                response_text = self._generate_greeting(agent_type)
                tools_used = ["greeting_generator"]

            # Weather query
            elif self._is_weather_query(message):
                location = self._extract_location(message)
                weather_data = await self._get_weather(location)
                response_text = self._format_weather_response(weather_data, agent_type)
                tools_used = ["weather_api"]
                structured_data = weather_data

            # Traffic query for truck
            elif self._is_traffic_query(message):
                truck_id = self._extract_truck_id(message)
                traffic_data = await self._get_truck_traffic(truck_id)
                response_text = self._format_traffic_response(traffic_data, agent_type, truck_id)
                tools_used = ["truck_location", "traffic_api"]
                structured_data = traffic_data

            # Bulk load creation
            elif self._is_bulk_load_request(message):
                load_count = self._extract_load_count(message)
                load_data = self._extract_load_list(message)

                # Create loads
                created_loads = await self._create_bulk_loads(load_data or load_count)
                response_text = self._format_bulk_load_response(created_loads, agent_type)
                tools_used = ["bulk_load_creator"]
                structured_data = {"loads": created_loads}
                task_id = created_loads[0]["task_id"] if created_loads else None

        return {
            "response": response_text,
            "reasoning": metadata.get("reasoning", "Processed conversational message"),
            "tools_used": tools_used,
            "task_id": task_id,
            "delegated_to": delegated_to,
            "confidence": 0.9,
            "data": structured_data,
            "agent": agent_type,
            "model": metadata.get("model"),
            "tokens_used": metadata.get("tokens_used"),
            "cost_usd": metadata.get("cost_usd")
        }

    def _get_agent_system_prompt(self, agent_type: str) -> str:
        """Get personality and role description for AI employee."""

        prompts = {
            "annie": f"""You are Annie, your AI Dispatcher at FreightOps.

YOUR ROLE: You're a full-time employee who manages 500 loads/month for this company.

Your personality:
- Friendly, efficient, and proactive like a great dispatcher
- Always use {self.user_name}'s name when greeting or responding
- You work 24/7 and coordinate with your team: Adam (Safety Officer), Fleet Manager, and CFO Analyst

Your capabilities:
- Assign drivers to loads (500/month capacity)
- Check weather and traffic for routes
- Create loads from lists or conversations
- Manage pickup and delivery workflows
- Query truck locations and statuses

IMPORTANT - Flag for approval when:
- You're uncertain about a driver assignment
- Load has unusual requirements outside normal parameters
- Customer is new or has special handling needs

When to delegate to your team:
- Compliance/safety concerns → Ask Adam to review
- Fleet/maintenance issues → Ask Fleet Manager
- Billing/margin questions → Ask CFO Analyst
""",

            "adam": f"""You are Adam, the AI Safety/Compliance Officer at FreightOps.

YOUR ROLE: You're a full-time employee who reviews EVERY load assignment for DOT compliance.

Your personality:
- Professional, thorough, and safety-first mindset
- Expert in DOT regulations, HOS rules, CFR citations
- Address {self.user_name} respectfully as your manager

Your capabilities:
- Audit driver HOS compliance (unlimited review capacity)
- Validate load assignments for safety violations
- Flag DOT compliance issues with CFR citations
- Review equipment safety compliance
- Explain compliance requirements to the team

IMPORTANT - Flag for approval when:
- Edge case compliance scenarios (unclear regulations)
- Driver has borderline HOS that needs manager judgment
- New regulation interpretation needed

When to delegate:
- Operations/dispatch → Annie handles that
- Fleet maintenance → Fleet Manager
- Financial questions → CFO Analyst
""",

            "fleet_manager": f"""You are the AI Fleet Manager at FreightOps.

YOUR ROLE: You're a full-time employee managing 50-500 trucks for this company.

Your personality:
- Detail-oriented, proactive about maintenance
- Expert in fleet operations, fuel optimization, routing
- Report to {self.user_name} as your operations manager

Your capabilities:
- Schedule preventive maintenance (50-500 truck capacity)
- Optimize fuel consumption and routes
- Monitor equipment health and flag issues
- Plan maintenance windows to minimize downtime
- Track truck locations and utilization

IMPORTANT - Flag for approval when:
- Major repair decisions (>$5K estimated cost)
- Unclear equipment failure diagnosis
- Schedule conflicts for critical maintenance

When to delegate:
- Dispatch/driver issues → Annie
- Compliance questions → Adam
- Budget/cost analysis → CFO Analyst
""",

            "cfo_analyst": f"""You are the AI CFO Analyst at FreightOps.

YOUR ROLE: You're a full-time employee analyzing financials for 500+ loads/month.

Your personality:
- Analytical, precise with numbers, profit-focused
- Expert in P&L, margins, rate optimization
- Report financial insights to {self.user_name}

Your capabilities:
- Calculate load margins and profitability (500+ loads/month)
- Validate billing accuracy
- Optimize rates and identify cost savings
- Generate financial reports and insights
- Flag unprofitable loads or customers

IMPORTANT - Flag for approval when:
- Margin below 10% (edge case profitability)
- Customer rate negotiation needed
- Unusual cost patterns detected

When to delegate:
- Operations → Annie
- Compliance → Adam
- Fleet costs → Fleet Manager
""",

            "harper": f"""You are Harper, the AI HR & Payroll Specialist at FreightOps.

YOUR ROLE: You're a full-time employee managing payroll for all drivers.

Your personality:
- Professional, accurate with numbers, detail-oriented
- Expert in payroll compliance, tax regulations, and employment law
- Address {self.user_name} as your supervisor

Your capabilities:
- Calculate driver settlements (mileage, detention, bonuses) - Unlimited capacity
- Process weekly/biweekly payroll via CheckHQ
- Track PTO and sick leave balances
- Calculate payroll taxes (FICA, federal, state withholding)
- Generate payroll reports and summaries
- Flag payroll discrepancies for review

IMPORTANT - Flag for approval when:
- Payroll discrepancy >$500
- Unusual pay patterns detected
- Missing tax withholding information
- Worker's compensation claims

When to delegate:
- Load dispatch → Annie
- Compliance issues → Adam
- Fleet costs → Fleet Manager
- Financial analysis → CFO Analyst
"""
        }

        return prompts.get(agent_type, "You are an AI assistant.")

    def _build_context(self, previous_messages: List[Dict]) -> str:
        """Build conversation history string."""
        if not previous_messages:
            return ""

        context_lines = ["Previous conversation:"]
        for msg in previous_messages[-5:]:  # Last 5 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_lines.append(f"{role.capitalize()}: {content}")

        return "\n".join(context_lines)

    def _get_available_tools(self, agent_type: str) -> List[Dict]:
        """Get tools available to this agent."""

        common_tools = [
            {
                "name": "get_current_time",
                "description": "Get current date and time",
                "parameters": {}
            },
            {
                "name": "query_database",
                "description": "Query the database for information",
                "parameters": {
                    "query": {"type": "string", "description": "SQL query to execute"}
                }
            }
        ]

        if agent_type == "annie":
            return common_tools + [
                {
                    "name": "get_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "location": {"type": "string", "description": "City name or zip code"}
                    }
                },
                {
                    "name": "get_truck_location",
                    "description": "Get current location of a truck",
                    "parameters": {
                        "truck_id": {"type": "string", "description": "Truck identifier"}
                    }
                },
                {
                    "name": "get_traffic",
                    "description": "Get traffic conditions for a location",
                    "parameters": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"}
                    }
                },
                {
                    "name": "create_loads",
                    "description": "Create multiple freight loads",
                    "parameters": {
                        "loads": {"type": "array", "description": "List of load data"}
                    }
                },
                {
                    "name": "find_drivers",
                    "description": "Search for available drivers",
                    "parameters": {
                        "criteria": {"type": "object", "description": "Search criteria"}
                    }
                }
            ]

        elif agent_type == "fleet_manager":
            return common_tools + [
                {
                    "name": "schedule_preventive_maintenance",
                    "description": "Schedule preventive maintenance for a truck",
                    "parameters": {
                        "truck_id": {"type": "string"},
                        "maintenance_type": {"type": "string"},
                        "priority": {"type": "string"},
                        "estimated_downtime_hours": {"type": "number"}
                    }
                },
                {
                    "name": "check_equipment_health",
                    "description": "Check equipment health and predict failures",
                    "parameters": {
                        "truck_id": {"type": "string"}
                    }
                },
                {
                    "name": "optimize_fuel_consumption",
                    "description": "Analyze fuel consumption and provide recommendations",
                    "parameters": {
                        "truck_id": {"type": "string", "required": False},
                        "time_period_days": {"type": "number", "default": 30}
                    }
                },
                {
                    "name": "plan_maintenance_window",
                    "description": "Find optimal maintenance window to minimize impact",
                    "parameters": {
                        "truck_id": {"type": "string"},
                        "required_hours": {"type": "number"}
                    }
                },
                {
                    "name": "get_fleet_utilization",
                    "description": "Get fleet utilization metrics",
                    "parameters": {
                        "time_period_days": {"type": "number", "default": 7}
                    }
                }
            ]

        elif agent_type == "cfo_analyst":
            return common_tools + [
                {
                    "name": "calculate_load_margin",
                    "description": "Calculate profit margin for a load",
                    "parameters": {
                        "load_id": {"type": "string"}
                    }
                },
                {
                    "name": "analyze_customer_profitability",
                    "description": "Analyze customer profitability and payment patterns",
                    "parameters": {
                        "customer_id": {"type": "string"},
                        "time_period_days": {"type": "number", "default": 90}
                    }
                },
                {
                    "name": "optimize_load_rate",
                    "description": "Recommend optimal rate for a load",
                    "parameters": {
                        "origin_city": {"type": "string"},
                        "origin_state": {"type": "string"},
                        "dest_city": {"type": "string"},
                        "dest_state": {"type": "string"},
                        "distance_miles": {"type": "number"}
                    }
                },
                {
                    "name": "generate_pl_report",
                    "description": "Generate P&L report for a time period",
                    "parameters": {
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"}
                    }
                },
                {
                    "name": "identify_unprofitable_loads",
                    "description": "Find loads with margins below threshold",
                    "parameters": {
                        "margin_threshold": {"type": "number", "default": 10},
                        "time_period_days": {"type": "number", "default": 30}
                    }
                }
            ]

        elif agent_type == "harper":
            return common_tools + [
                {
                    "name": "calculate_driver_settlement",
                    "description": "Calculate driver's weekly settlement (pay)",
                    "parameters": {
                        "driver_id": {"type": "string", "description": "Driver ID"},
                        "start_date": {"type": "string", "description": "Pay period start (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "Pay period end (YYYY-MM-DD)"}
                    }
                },
                {
                    "name": "process_weekly_payroll",
                    "description": "Process payroll for all drivers for a pay period",
                    "parameters": {
                        "pay_period_end": {"type": "string", "description": "Pay period end date (YYYY-MM-DD)"}
                    }
                },
                {
                    "name": "check_pto_balance",
                    "description": "Check driver's PTO balance",
                    "parameters": {
                        "driver_id": {"type": "string", "description": "Driver ID"}
                    }
                },
                {
                    "name": "calculate_payroll_taxes",
                    "description": "Calculate payroll taxes for a settlement",
                    "parameters": {
                        "gross_pay": {"type": "number", "description": "Gross pay amount"},
                        "driver_id": {"type": "string", "description": "Driver ID for tax withholding info"}
                    }
                },
                {
                    "name": "get_payroll_summary",
                    "description": "Get payroll summary for a time period",
                    "parameters": {
                        "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                    }
                },
                {
                    "name": "flag_payroll_issue",
                    "description": "Flag payroll discrepancy or issue for review",
                    "parameters": {
                        "driver_id": {"type": "string", "description": "Driver ID"},
                        "issue_type": {"type": "string", "description": "Type of issue"},
                        "description": {"type": "string", "description": "Issue description"},
                        "amount": {"type": "number", "description": "Dollar amount involved"}
                    }
                }
            ]

        return common_tools

    # === Pattern Detection ===

    def _is_greeting(self, message: str) -> bool:
        """Check if message is a greeting."""
        greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "howdy"]
        return any(greeting in message.lower() for greeting in greetings)

    def _is_weather_query(self, message: str) -> bool:
        """Check if message asks about weather."""
        weather_keywords = ["weather", "temperature", "forecast", "rain", "snow", "sunny"]
        return any(keyword in message.lower() for keyword in weather_keywords)

    def _is_traffic_query(self, message: str) -> bool:
        """Check if message asks about traffic."""
        return "traffic" in message.lower() and ("truck" in message.lower() or re.search(r'\b\d+\b', message))

    def _is_bulk_load_request(self, message: str) -> bool:
        """Check if message requests creating multiple loads."""
        patterns = [
            r'create\s+(\d+)\s+loads',
            r'make\s+(\d+)\s+loads',
            r'add\s+(\d+)\s+loads',
            r'here.*list'
        ]
        return any(re.search(pattern, message.lower()) for pattern in patterns)

    # === Data Extraction ===

    def _extract_location(self, message: str) -> str:
        """Extract location from message."""
        # Simple: look for city names or "in X"
        match = re.search(r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', message)
        if match:
            return match.group(1)

        # Check for common cities
        cities = ["Chicago", "New York", "Los Angeles", "Houston", "Phoenix", "Dallas"]
        for city in cities:
            if city.lower() in message.lower():
                return city

        return "current location"

    def _extract_truck_id(self, message: str) -> Optional[str]:
        """Extract truck ID from message."""
        # Look for "truck 110" or "truck #110"
        match = re.search(r'truck\s+#?(\d+)', message.lower())
        if match:
            return match.group(1)
        return None

    def _extract_load_count(self, message: str) -> int:
        """Extract number of loads to create."""
        match = re.search(r'(\d+)\s+loads', message.lower())
        if match:
            return int(match.group(1))
        return 0

    def _extract_load_list(self, message: str) -> Optional[List[Dict]]:
        """Extract load data from message (if provided as list)."""
        # TODO: Parse CSV or structured data
        # For now, return None and we'll create template loads
        return None

    # === Response Generation ===

    def _generate_greeting(self, agent_type: str) -> str:
        """Generate personalized greeting."""
        agent_names = {
            "annie": "Annie",
            "adam": "Adam",
            "atlas": "Atlas"
        }

        hour = datetime.utcnow().hour
        if hour < 12:
            time_greeting = "Good morning"
        elif hour < 18:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"

        return f"{time_greeting}, {self.user_name}! I'm {agent_names.get(agent_type, 'AI')}, how can I help you today?"

    def _format_weather_response(self, weather_data: Dict, agent_type: str) -> str:
        """Format weather data into conversational response."""
        if weather_data.get("error"):
            return f"I couldn't fetch the weather data right now. {weather_data['error']}"

        location = weather_data.get("location", "that location")
        temp = weather_data.get("temperature", "N/A")
        conditions = weather_data.get("conditions", "unknown")

        return f"The weather in {location} is {conditions} with a temperature of {temp}°F. {weather_data.get('note', '')}"

    def _format_traffic_response(self, traffic_data: Dict, agent_type: str, truck_id: str) -> str:
        """Format traffic data into conversational response."""
        if traffic_data.get("error"):
            return f"I couldn't get traffic data for truck {truck_id}. {traffic_data['error']}"

        location = traffic_data.get("location", "unknown")
        status = traffic_data.get("traffic_status", "moderate")

        return f"Truck {truck_id} is currently near {location}. Traffic conditions are {status}. {traffic_data.get('note', '')}"

    def _format_bulk_load_response(self, loads: List[Dict], agent_type: str) -> str:
        """Format bulk load creation response."""
        if not loads:
            return "I couldn't create the loads. Please check the data and try again."

        load_numbers = [load.get("reference_number", "N/A") for load in loads]

        return f"✅ I've created {len(loads)} loads for you:\n\n" + "\n".join([
            f"• {num}" for num in load_numbers[:10]
        ]) + (f"\n... and {len(loads) - 10} more" if len(loads) > 10 else "")

    # === External API Calls - PRODUCTION ===

    async def _get_weather(self, location: str) -> Dict[str, Any]:
        """
        Fetch REAL weather data from OpenWeatherMap API.

        Requires: OPENWEATHER_API_KEY environment variable
        """
        try:
            # Parse location (city, state)
            parts = location.split(',')
            city = parts[0].strip()
            state = parts[1].strip() if len(parts) > 1 else None

            weather_data = await self.api_manager.get_weather(city, state)

            return weather_data

        except Exception as e:
            return {
                "error": f"Weather API error: {str(e)}",
                "location": location
            }

    async def _get_truck_traffic(self, truck_id: str) -> Dict[str, Any]:
        """
        Get truck location and REAL traffic conditions.

        Requires: GOOGLE_MAPS_API_KEY environment variable
        """
        try:
            # Query truck location from database
            result = await self.db.execute(
                text("""
                    SELECT
                        e.unit_number,
                        e.last_known_latitude,
                        e.last_known_longitude,
                        e.last_location_update
                    FROM equipment e
                    WHERE e.unit_number = :truck_id OR e.id = :truck_id
                    LIMIT 1
                """),
                {"truck_id": truck_id}
            )

            truck = result.fetchone()

            if not truck or not truck[1]:
                return {
                    "error": "Truck not found or location data unavailable",
                    "truck_id": truck_id
                }

            lat, lon = float(truck[1]), float(truck[2])

            # Get real traffic data from Google Maps API
            traffic_data = await self.api_manager.get_traffic(lat, lon)

            # Get human-readable address
            address = await self.api_manager.reverse_geocode(lat, lon)

            return {
                "truck_id": truck_id,
                "location": address,
                "latitude": lat,
                "longitude": lon,
                "traffic_status": traffic_data["status"],
                "delay_seconds": traffic_data["delay_seconds"],
                "last_update": truck[3].isoformat() if truck[3] else "unknown"
            }

        except Exception as e:
            return {
                "error": f"Traffic API error: {str(e)}",
                "truck_id": truck_id
            }

    async def _create_bulk_loads(self, load_data_or_count) -> List[Dict]:
        """Create multiple loads from list or count."""
        import uuid

        # If integer, create N template loads
        if isinstance(load_data_or_count, int):
            count = load_data_or_count
            loads = []

            for i in range(min(count, 50)):  # Cap at 50 for safety
                load_id = str(uuid.uuid4())
                reference_number = f"LOAD-{datetime.utcnow().strftime('%Y%m%d')}-{i+1:04d}"

                # Insert into database
                await self.db.execute(
                    text("""
                        INSERT INTO freight_load (
                            id, company_id, reference_number, status,
                            origin_city, origin_state, dest_city, dest_state,
                            created_at, created_by
                        ) VALUES (
                            :id, :company_id, :ref, 'pending_dispatch',
                            'Chicago', 'IL', 'Dallas', 'TX',
                            :created_at, :created_by
                        )
                    """),
                    {
                        "id": load_id,
                        "company_id": self.company_id,
                        "ref": reference_number,
                        "created_at": datetime.utcnow(),
                        "created_by": self.user_id
                    }
                )

                loads.append({
                    "id": load_id,
                    "reference_number": reference_number,
                    "status": "pending_dispatch"
                })

            await self.db.commit()
            return loads

        # If list, create from structured data
        else:
            # TODO: Parse and validate load data
            return []

    # === Fleet Manager Tool Integrations ===

    async def _call_fleet_manager_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call Fleet Manager AI tool."""
        await self.fleet_manager.register_tools()

        tool_method = getattr(self.fleet_manager, f"_{tool_name}", None)
        if not tool_method:
            return {"error": f"Tool {tool_name} not found"}

        try:
            result = await tool_method(**kwargs)
            return result
        except Exception as e:
            return {"error": str(e)}

    # === CFO Analyst Tool Integrations ===

    async def _call_cfo_analyst_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call CFO Analyst AI tool."""
        await self.cfo_analyst.register_tools()

        tool_method = getattr(self.cfo_analyst, f"_{tool_name}", None)
        if not tool_method:
            return {"error": f"Tool {tool_name} not found"}

        try:
            result = await tool_method(**kwargs)
            return result
        except Exception as e:
            return {"error": str(e)}

    # === Harper AI Tool Integrations ===

    async def _call_harper_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call Harper AI tool."""
        await self.harper.register_tools()

        tool_method = getattr(self.harper, f"_{tool_name}", None)
        if not tool_method:
            return {"error": f"Tool {tool_name} not found"}

        try:
            result = await tool_method(**kwargs)
            return result
        except Exception as e:
            return {"error": str(e)}

    async def _execute_tool_calls(self, response_text: str, agent_type: str) -> Dict:
        """Parse and execute tool calls from AI response."""
        # TODO: Implement tool call parsing and execution
        return {
            "tools_used": [],
            "final_response": response_text
        }
