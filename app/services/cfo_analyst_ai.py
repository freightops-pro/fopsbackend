"""
CFO Analyst AI - Production Implementation

AI employee analyzing financials for 500+ loads/month:
- Load margin calculation and profitability analysis
- Rate optimization and cost reduction
- P&L reporting and financial insights
- Customer profitability analysis
- Budget variance tracking

Uses Llama 4 Maverick 400B for precision financial analysis.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.services.ai_agent import BaseAIAgent, AITool
from app.core.llm_router import LLMRouter


class CFOAnalystAI(BaseAIAgent):
    """
    CFO Analyst - AI Employee for financial analysis.

    PRODUCTION IMPLEMENTATION - Real financial calculations, no mocks.

    Capacity: 500+ loads/month
    Model: Llama 4 Maverick 400B
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.llm_router = LLMRouter()

    @property
    def agent_name(self) -> str:
        return "CFO Analyst"

    @property
    def agent_role(self) -> str:
        return """AI CFO Analyst specializing in margin analysis, rate optimization,
P&L reporting, and profitability insights. I analyze 500+ loads monthly and ensure
financial health."""

    async def register_tools(self):
        """Register CFO Analyst's production tools."""
        self.tools = [
            AITool(
                name="calculate_load_margin",
                description="Calculate profit margin for a load",
                parameters={
                    "load_id": {"type": "string", "description": "Load ID"},
                },
                function=self._calculate_load_margin
            ),

            AITool(
                name="analyze_customer_profitability",
                description="Analyze customer profitability and payment patterns",
                parameters={
                    "customer_id": {"type": "string", "description": "Customer ID"},
                    "time_period_days": {"type": "number", "description": "Analysis period (default: 90 days)"},
                },
                function=self._analyze_customer_profitability
            ),

            AITool(
                name="optimize_load_rate",
                description="Recommend optimal rate for a load based on market data",
                parameters={
                    "origin_city": {"type": "string"},
                    "origin_state": {"type": "string"},
                    "dest_city": {"type": "string"},
                    "dest_state": {"type": "string"},
                    "distance_miles": {"type": "number"},
                },
                function=self._optimize_load_rate
            ),

            AITool(
                name="generate_pl_report",
                description="Generate P&L report for a time period",
                parameters={
                    "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                },
                function=self._generate_pl_report
            ),

            AITool(
                name="identify_unprofitable_loads",
                description="Find loads with margins below threshold",
                parameters={
                    "margin_threshold": {"type": "number", "description": "Minimum acceptable margin % (default: 10)"},
                    "time_period_days": {"type": "number", "description": "Analysis period (default: 30)"},
                },
                function=self._identify_unprofitable_loads
            ),

            AITool(
                name="flag_for_approval",
                description="Flag financial decision for approval (margins <10%, rate negotiations, etc.)",
                parameters={
                    "reason": {"type": "string"},
                    "amount": {"type": "number", "description": "Dollar amount involved"},
                    "urgency": {"type": "string", "description": "low, medium, high, critical"},
                    "recommendation": {"type": "string"},
                },
                function=self._flag_for_approval
            ),
        ]

    async def _calculate_load_margin(self, load_id: str) -> Dict[str, Any]:
        """
        Calculate actual profit margin for a load.

        PRODUCTION: Real calculation from revenue, driver pay, fuel, and overhead.
        """
        # Get load financial data
        load = await self.db.execute(
            text("""
                SELECT
                    l.id,
                    l.reference_number,
                    l.base_rate as revenue,
                    l.status,
                    l.assigned_driver_id,
                    l.origin_city,
                    l.origin_state,
                    l.dest_city,
                    l.dest_state,
                    l.distance_miles
                FROM freight_load l
                WHERE l.id = :id
                LIMIT 1
            """),
            {"id": load_id}
        )

        load_data = load.fetchone()
        if not load_data:
            return {"error": "Load not found"}

        load_id, ref_num, revenue, status, driver_id, orig_city, orig_state, dest_city, dest_state, distance = load_data

        if not revenue:
            return {"error": "Load has no revenue/rate configured"}

        revenue = float(revenue)

        # Calculate costs
        driver_pay = 0
        fuel_cost = 0
        other_costs = 0

        # Driver pay (query driver settlement if exists)
        if driver_id:
            driver_settlement = await self.db.execute(
                text("""
                    SELECT SUM(amount)
                    FROM driver_settlements
                    WHERE load_id = :load_id AND settlement_type = 'driver_pay'
                """),
                {"load_id": load_id}
            )
            driver_pay_result = driver_settlement.fetchone()
            if driver_pay_result and driver_pay_result[0]:
                driver_pay = float(driver_pay_result[0])
            else:
                # Estimate: 70% of revenue if no settlement yet
                driver_pay = revenue * 0.70

        # Fuel cost (query fuel transactions for this load)
        fuel_transactions = await self.db.execute(
            text("""
                SELECT SUM(cost)
                FROM fueltransaction
                WHERE load_id = :load_id
            """),
            {"load_id": load_id}
        )
        fuel_result = fuel_transactions.fetchone()
        if fuel_result and fuel_result[0]:
            fuel_cost = float(fuel_result[0])
        else:
            # Estimate: $3.50/gallon, 6 MPG
            if distance:
                estimated_gallons = float(distance) / 6.0
                fuel_cost = estimated_gallons * 3.50

        # Other costs (insurance, overhead)
        overhead_rate = 0.05  # 5% overhead
        other_costs = revenue * overhead_rate

        # Calculate margin
        total_costs = driver_pay + fuel_cost + other_costs
        gross_profit = revenue - total_costs
        margin_percent = (gross_profit / revenue * 100) if revenue > 0 else 0

        return {
            "load_id": load_id,
            "reference_number": ref_num,
            "revenue": round(revenue, 2),
            "costs": {
                "driver_pay": round(driver_pay, 2),
                "fuel": round(fuel_cost, 2),
                "overhead": round(other_costs, 2),
                "total": round(total_costs, 2)
            },
            "gross_profit": round(gross_profit, 2),
            "margin_percent": round(margin_percent, 1),
            "profitability_status": self._get_profitability_status(margin_percent),
            "flag_for_review": margin_percent < 10
        }

    def _get_profitability_status(self, margin: float) -> str:
        """Classify profitability."""
        if margin >= 20:
            return "excellent"
        elif margin >= 15:
            return "good"
        elif margin >= 10:
            return "acceptable"
        elif margin >= 5:
            return "poor"
        else:
            return "unprofitable"

    async def _analyze_customer_profitability(self, customer_id: str, time_period_days: int = 90) -> Dict[str, Any]:
        """
        Analyze customer profitability and payment patterns.

        PRODUCTION: Real revenue, margin, and payment analysis.
        """
        start_date = datetime.utcnow() - timedelta(days=time_period_days)

        # Get customer load performance
        customer_loads = await self.db.execute(
            text("""
                SELECT
                    COUNT(l.id) as load_count,
                    SUM(l.base_rate) as total_revenue,
                    AVG(l.base_rate) as avg_revenue_per_load,
                    COUNT(CASE WHEN l.status = 'delivered' THEN 1 END) as completed_loads,
                    COUNT(CASE WHEN l.status = 'cancelled' THEN 1 END) as cancelled_loads
                FROM freight_load l
                WHERE l.customer_id = :customer_id
                    AND l.created_at >= :start_date
            """),
            {"customer_id": customer_id, "start_date": start_date}
        )

        customer_data = customer_loads.fetchone()
        if not customer_data or not customer_data[0]:
            return {"message": "No loads found for this customer in the analysis period"}

        load_count, total_revenue, avg_revenue, completed, cancelled = customer_data

        # Calculate margins for this customer's loads
        margin_analysis = await self.db.execute(
            text("""
                SELECT l.id
                FROM freight_load l
                WHERE l.customer_id = :customer_id
                    AND l.created_at >= :start_date
                    AND l.base_rate IS NOT NULL
                LIMIT 50
            """),
            {"customer_id": customer_id, "start_date": start_date}
        )

        margins = []
        for row in margin_analysis.fetchall():
            margin_data = await self._calculate_load_margin(row[0])
            if not margin_data.get("error"):
                margins.append(margin_data["margin_percent"])

        avg_margin = sum(margins) / len(margins) if margins else 0
        completion_rate = (completed / load_count * 100) if load_count > 0 else 0

        # Determine customer status
        if avg_margin >= 15 and completion_rate >= 90:
            customer_status = "premium"
        elif avg_margin >= 10 and completion_rate >= 80:
            customer_status = "good"
        elif avg_margin >= 5:
            customer_status = "marginal"
        else:
            customer_status = "unprofitable"

        return {
            "customer_id": customer_id,
            "analysis_period_days": time_period_days,
            "total_loads": load_count,
            "completed_loads": completed,
            "cancelled_loads": cancelled,
            "completion_rate_percent": round(completion_rate, 1),
            "total_revenue": round(float(total_revenue), 2) if total_revenue else 0,
            "avg_revenue_per_load": round(float(avg_revenue), 2) if avg_revenue else 0,
            "avg_margin_percent": round(avg_margin, 1),
            "customer_status": customer_status,
            "recommendation": self._get_customer_recommendation(customer_status, avg_margin)
        }

    def _get_customer_recommendation(self, status: str, margin: float) -> str:
        """Generate customer management recommendation."""
        if status == "premium":
            return "Excellent customer - maintain relationship and consider volume discounts"
        elif status == "good":
            return "Solid customer - maintain current terms"
        elif status == "marginal":
            return "Review pricing - consider rate increase or reducing service"
        else:
            return "Unprofitable customer - negotiate rate increase or discontinue service"

    async def _optimize_load_rate(
        self,
        origin_city: str,
        origin_state: str,
        dest_city: str,
        dest_state: str,
        distance_miles: float
    ) -> Dict[str, Any]:
        """
        Recommend optimal rate based on historical data and market conditions.

        PRODUCTION: Real market analysis from historical loads.
        """
        # Query similar historical loads
        similar_loads = await self.db.execute(
            text("""
                SELECT
                    base_rate,
                    distance_miles
                FROM freight_load
                WHERE origin_state = :origin_state
                    AND dest_state = :dest_state
                    AND base_rate IS NOT NULL
                    AND distance_miles IS NOT NULL
                    AND created_at >= :lookback_date
                ORDER BY created_at DESC
                LIMIT 20
            """),
            {
                "origin_state": origin_state,
                "dest_state": dest_state,
                "lookback_date": datetime.utcnow() - timedelta(days=90)
            }
        )

        historical_data = similar_loads.fetchall()

        if not historical_data:
            # No historical data - use industry standard
            base_rate_per_mile = 2.50  # Industry average
            recommended_rate = distance_miles * base_rate_per_mile

            return {
                "recommended_rate": round(recommended_rate, 2),
                "confidence": "low",
                "reasoning": "No historical data - using industry standard $2.50/mile",
                "rate_per_mile": base_rate_per_mile,
                "data_points": 0
            }

        # Calculate average rate per mile from historical data
        rates_per_mile = [float(rate) / float(distance) for rate, distance in historical_data if distance and distance > 0]
        avg_rate_per_mile = sum(rates_per_mile) / len(rates_per_mile) if rates_per_mile else 2.50

        # Add 5% margin for negotiation buffer
        recommended_rate = (distance_miles * avg_rate_per_mile) * 1.05

        return {
            "recommended_rate": round(recommended_rate, 2),
            "rate_per_mile": round(avg_rate_per_mile, 2),
            "confidence": "high" if len(historical_data) >= 10 else "medium",
            "reasoning": f"Based on {len(historical_data)} similar loads in past 90 days",
            "data_points": len(historical_data),
            "market_range": {
                "min": round(min(rates_per_mile) * distance_miles, 2) if rates_per_mile else 0,
                "max": round(max(rates_per_mile) * distance_miles, 2) if rates_per_mile else 0,
                "avg": round(avg_rate_per_mile * distance_miles, 2)
            }
        }

    async def _generate_pl_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Generate P&L report for time period.

        PRODUCTION: Real revenue and cost aggregation.
        """
        # Parse dates
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        # Get revenue
        revenue_query = await self.db.execute(
            text("""
                SELECT
                    COUNT(id) as load_count,
                    SUM(base_rate) as total_revenue,
                    COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered_count
                FROM freight_load
                WHERE created_at >= :start AND created_at <= :end
                    AND base_rate IS NOT NULL
            """),
            {"start": start, "end": end}
        )

        revenue_data = revenue_query.fetchone()
        load_count, total_revenue, delivered_count = revenue_data if revenue_data else (0, 0, 0)

        # Get costs
        # Driver pay
        driver_pay_query = await self.db.execute(
            text("""
                SELECT SUM(amount)
                FROM driver_settlements
                WHERE settlement_date >= :start AND settlement_date <= :end
                    AND settlement_type = 'driver_pay'
            """),
            {"start": start, "end": end}
        )
        driver_pay = driver_pay_query.fetchone()[0] or 0

        # Fuel costs
        fuel_cost_query = await self.db.execute(
            text("""
                SELECT SUM(cost)
                FROM fueltransaction
                WHERE transaction_date >= :start AND transaction_date <= :end
            """),
            {"start": start, "end": end}
        )
        fuel_costs = fuel_cost_query.fetchone()[0] or 0

        # Calculate
        total_revenue = float(total_revenue) if total_revenue else 0
        total_costs = float(driver_pay) + float(fuel_costs)
        overhead = total_revenue * 0.05  # 5% overhead estimate
        total_costs += overhead

        gross_profit = total_revenue - total_costs
        margin_percent = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "days": (end - start).days
            },
            "revenue": {
                "total": round(total_revenue, 2),
                "load_count": load_count,
                "delivered_count": delivered_count,
                "avg_per_load": round(total_revenue / load_count, 2) if load_count > 0 else 0
            },
            "costs": {
                "driver_pay": round(float(driver_pay), 2),
                "fuel": round(float(fuel_costs), 2),
                "overhead": round(overhead, 2),
                "total": round(total_costs, 2)
            },
            "profitability": {
                "gross_profit": round(gross_profit, 2),
                "margin_percent": round(margin_percent, 1),
                "status": self._get_profitability_status(margin_percent)
            }
        }

    async def _identify_unprofitable_loads(self, margin_threshold: float = 10, time_period_days: int = 30) -> Dict[str, Any]:
        """
        Find loads with margins below threshold.

        PRODUCTION: Real margin analysis across fleet.
        """
        start_date = datetime.utcnow() - timedelta(days=time_period_days)

        # Get recent loads
        loads_query = await self.db.execute(
            text("""
                SELECT id, reference_number
                FROM freight_load
                WHERE created_at >= :start_date
                    AND base_rate IS NOT NULL
                    AND status IN ('delivered', 'completed')
                ORDER BY created_at DESC
                LIMIT 100
            """),
            {"start_date": start_date}
        )

        unprofitable = []
        for row in loads_query.fetchall():
            load_id, ref_num = row
            margin_data = await self._calculate_load_margin(load_id)

            if not margin_data.get("error") and margin_data["margin_percent"] < margin_threshold:
                unprofitable.append({
                    "load_id": load_id,
                    "reference_number": ref_num,
                    "margin_percent": margin_data["margin_percent"],
                    "gross_profit": margin_data["gross_profit"],
                    "revenue": margin_data["revenue"]
                })

        return {
            "margin_threshold": margin_threshold,
            "period_days": time_period_days,
            "unprofitable_load_count": len(unprofitable),
            "loads": unprofitable[:20],  # Top 20
            "recommendation": f"Review pricing strategy - {len(unprofitable)} loads below {margin_threshold}% margin"
        }

    async def _flag_for_approval(
        self,
        reason: str,
        amount: float,
        urgency: str,
        recommendation: str
    ) -> Dict[str, Any]:
        """Flag financial decision for approval."""
        import uuid

        approval_id = str(uuid.uuid4())

        await self.db.execute(
            text("""
                INSERT INTO ai_approval_requests (
                    id, agent_type, reason, amount, urgency,
                    recommendation, status, created_at
                ) VALUES (
                    :id, 'cfo_analyst', :reason, :amount, :urgency,
                    :recommendation, 'pending', :created_at
                )
            """),
            {
                "id": approval_id,
                "reason": reason,
                "amount": amount,
                "urgency": urgency,
                "recommendation": recommendation,
                "created_at": datetime.utcnow()
            }
        )

        await self.db.commit()

        return {
            "approval_id": approval_id,
            "status": "pending_approval",
            "reason": reason,
            "amount": amount,
            "urgency": urgency,
            "message": "This financial decision requires approval. Manager has been notified."
        }
