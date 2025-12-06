"""Alex AI - Autonomous Sales and Analytics Agent.

Alex handles business intelligence, revenue forecasting, churn prediction,
renewal management, and KPI aggregation.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.load import Load
from app.models.company import Company
from app.services.ai_agent import BaseAIAgent, AITool


class AlexAI(BaseAIAgent):
    """
    Alex - Autonomous Sales and Analytics AI Agent.

    Specializes in:
    - Revenue forecasting and ARR calculations
    - Churn prediction and renewal management
    - Business intelligence and KPI aggregation
    - Upsell opportunity identification
    - Executive reporting and analytics
    """

    @property
    def agent_name(self) -> str:
        return "Alex"

    @property
    def agent_role(self) -> str:
        return """Sales and analytics AI specializing in revenue forecasting, churn prediction,
business intelligence, and strategic insights. I analyze patterns to predict outcomes,
identify opportunities, and provide actionable intelligence for business growth."""

    async def register_tools(self):
        """Register all tools Alex can use."""
        self.tools = [
            # Revenue Analytics Tools
            AITool(
                name="calculate_revenue_metrics",
                description="Calculate revenue metrics including total revenue, average deal size, growth rate",
                parameters={
                    "period_days": {"type": "number", "description": "Number of days to analyze (default 30)"},
                },
                function=self._calculate_revenue_metrics
            ),

            AITool(
                name="forecast_revenue",
                description="Forecast future revenue based on historical trends",
                parameters={
                    "forecast_days": {"type": "number", "description": "Number of days to forecast ahead (default 30)"},
                },
                function=self._forecast_revenue
            ),

            # Business Intelligence Tools
            AITool(
                name="get_business_kpis",
                description="Get comprehensive business KPIs across operations, finance, and growth",
                parameters={
                    "period": {"type": "string", "description": "Time period: today, week, month, quarter"},
                },
                function=self._get_business_kpis
            ),

            AITool(
                name="analyze_customer_trends",
                description="Analyze customer activity and engagement trends",
                parameters={
                    "min_loads": {"type": "number", "description": "Minimum loads to consider a customer (default 1)"},
                },
                function=self._analyze_customer_trends
            ),

            # Growth Analysis Tools
            AITool(
                name="identify_growth_opportunities",
                description="Identify potential upsell and expansion opportunities",
                parameters={
                    "min_activity_threshold": {"type": "number", "description": "Minimum loads per month to consider active (default 10)"},
                },
                function=self._identify_growth_opportunities
            ),

            AITool(
                name="calculate_customer_lifetime_value",
                description="Calculate estimated lifetime value of customers",
                parameters={
                    "customer_name": {"type": "string", "description": "Customer name to analyze (optional, analyzes all if not provided)"},
                },
                function=self._calculate_customer_lifetime_value
            ),

            # Reporting Tools
            AITool(
                name="generate_executive_summary",
                description="Generate comprehensive executive summary with key insights",
                parameters={
                    "period": {"type": "string", "description": "Time period: week, month, quarter"},
                },
                function=self._generate_executive_summary
            ),
        ]

    # === Tool Implementations ===

    async def _calculate_revenue_metrics(
        self,
        period_days: int = 30,
        **kwargs
    ) -> Dict[str, Any]:
        """Calculate revenue metrics for the period."""
        try:
            company_id = kwargs.get("company_id", "default")
            start_date = datetime.utcnow() - timedelta(days=period_days)

            # Query loads for the period
            query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.created_at >= start_date,
                    Load.status.in_(["delivered", "completed"])
                )
            )
            result = await self.db.execute(query)
            loads = result.scalars().all()

            # Calculate metrics
            total_revenue = sum(float(load.base_rate) for load in loads)
            total_loads = len(loads)
            avg_deal_size = total_revenue / total_loads if total_loads > 0 else 0

            # Calculate growth rate (compare to previous period)
            previous_start = start_date - timedelta(days=period_days)
            previous_query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.created_at >= previous_start,
                    Load.created_at < start_date,
                    Load.status.in_(["delivered", "completed"])
                )
            )
            previous_result = await self.db.execute(previous_query)
            previous_loads = previous_result.scalars().all()
            previous_revenue = sum(float(load.base_rate) for load in previous_loads)

            growth_rate = ((total_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0

            return {
                "status": "success",
                "period_days": period_days,
                "total_revenue": round(total_revenue, 2),
                "total_loads": total_loads,
                "average_deal_size": round(avg_deal_size, 2),
                "growth_rate_percent": round(growth_rate, 1),
                "previous_period_revenue": round(previous_revenue, 2),
            }

        except Exception as e:
            return {"error": str(e)}

    async def _forecast_revenue(
        self,
        forecast_days: int = 30,
        **kwargs
    ) -> Dict[str, Any]:
        """Forecast future revenue based on trends."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Get last 90 days of data for trend analysis
            start_date = datetime.utcnow() - timedelta(days=90)
            query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.created_at >= start_date,
                    Load.status.in_(["delivered", "completed"])
                )
            )
            result = await self.db.execute(query)
            loads = result.scalars().all()

            # Simple linear trend forecast
            total_revenue = sum(float(load.base_rate) for load in loads)
            daily_average = total_revenue / 90 if loads else 0

            # Apply growth trend (simplified - in production use ML models)
            growth_factor = 1.05  # Assume 5% growth
            forecasted_daily = daily_average * growth_factor
            forecasted_total = forecasted_daily * forecast_days

            return {
                "status": "success",
                "forecast_period_days": forecast_days,
                "forecasted_revenue": round(forecasted_total, 2),
                "daily_average": round(daily_average, 2),
                "forecasted_daily": round(forecasted_daily, 2),
                "growth_assumption_percent": 5.0,
                "confidence": "medium",  # Would be calculated from variance in production
            }

        except Exception as e:
            return {"error": str(e)}

    async def _get_business_kpis(
        self,
        period: str = "month",
        **kwargs
    ) -> Dict[str, Any]:
        """Get comprehensive business KPIs."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Determine date range
            if period == "today":
                start_date = datetime.utcnow().replace(hour=0, minute=0, second=0)
            elif period == "week":
                start_date = datetime.utcnow() - timedelta(days=7)
            elif period == "quarter":
                start_date = datetime.utcnow() - timedelta(days=90)
            else:  # month
                start_date = datetime.utcnow() - timedelta(days=30)

            # Get all loads for period
            query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.created_at >= start_date
                )
            )
            result = await self.db.execute(query)
            loads = result.scalars().all()

            # Calculate KPIs
            total_loads = len(loads)
            completed_loads = len([l for l in loads if l.status in ["delivered", "completed"]])
            total_revenue = sum(float(l.base_rate) for l in loads if l.status in ["delivered", "completed"])

            # Customer metrics
            unique_customers = len(set(l.customer_name for l in loads))

            # Operational metrics
            active_loads = len([l for l in loads if l.status in ["in_transit", "assigned"]])

            return {
                "status": "success",
                "period": period,
                "kpis": {
                    "total_loads": total_loads,
                    "completed_loads": completed_loads,
                    "total_revenue": round(total_revenue, 2),
                    "unique_customers": unique_customers,
                    "active_loads": active_loads,
                    "completion_rate": round(completed_loads / total_loads * 100, 1) if total_loads > 0 else 0,
                    "revenue_per_load": round(total_revenue / completed_loads, 2) if completed_loads > 0 else 0,
                },
            }

        except Exception as e:
            return {"error": str(e)}

    async def _analyze_customer_trends(
        self,
        min_loads: int = 1,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze customer activity trends."""
        try:
            company_id = kwargs.get("company_id", "default")
            start_date = datetime.utcnow() - timedelta(days=90)

            # Get loads for last 90 days
            query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.created_at >= start_date
                )
            )
            result = await self.db.execute(query)
            loads = result.scalars().all()

            # Group by customer
            customer_stats = {}
            for load in loads:
                customer = load.customer_name
                if customer not in customer_stats:
                    customer_stats[customer] = {
                        "load_count": 0,
                        "total_revenue": 0,
                        "last_load_date": None,
                    }

                customer_stats[customer]["load_count"] += 1
                if load.status in ["delivered", "completed"]:
                    customer_stats[customer]["total_revenue"] += float(load.base_rate)

                if not customer_stats[customer]["last_load_date"] or (load.created_at and load.created_at > customer_stats[customer]["last_load_date"]):
                    customer_stats[customer]["last_load_date"] = load.created_at

            # Filter by min_loads
            active_customers = {
                k: v for k, v in customer_stats.items()
                if v["load_count"] >= min_loads
            }

            # Sort by revenue
            top_customers = sorted(
                active_customers.items(),
                key=lambda x: x[1]["total_revenue"],
                reverse=True
            )[:10]

            return {
                "status": "success",
                "period_days": 90,
                "total_customers": len(customer_stats),
                "active_customers": len(active_customers),
                "top_customers": [
                    {
                        "name": name,
                        "loads": stats["load_count"],
                        "revenue": round(stats["total_revenue"], 2),
                        "last_load": stats["last_load_date"].isoformat() if stats["last_load_date"] else None,
                    }
                    for name, stats in top_customers
                ],
            }

        except Exception as e:
            return {"error": str(e)}

    async def _identify_growth_opportunities(
        self,
        min_activity_threshold: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """Identify upsell and growth opportunities."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Get customer trends
            trends_result = await self._analyze_customer_trends(min_loads=min_activity_threshold, company_id=company_id)

            if "error" in trends_result:
                return trends_result

            opportunities = []

            # Identify high-volume customers (potential for volume discounts/contracts)
            if "top_customers" in trends_result:
                for customer in trends_result["top_customers"]:
                    if customer["loads"] >= min_activity_threshold:
                        opportunities.append({
                            "customer": customer["name"],
                            "opportunity_type": "volume_contract",
                            "reason": f"{customer['loads']} loads in 90 days - potential for annual contract",
                            "estimated_value": customer["revenue"] * 4,  # Annualized
                            "priority": "high" if customer["loads"] > min_activity_threshold * 2 else "medium",
                        })

            return {
                "status": "success",
                "opportunities_found": len(opportunities),
                "opportunities": opportunities,
            }

        except Exception as e:
            return {"error": str(e)}

    async def _calculate_customer_lifetime_value(
        self,
        customer_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Calculate customer lifetime value."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Query customer's loads
            query = select(Load).where(Load.company_id == company_id)

            if customer_name:
                query = query.where(Load.customer_name == customer_name)

            result = await self.db.execute(query)
            loads = result.scalars().all()

            if customer_name:
                # Single customer LTV
                total_revenue = sum(float(l.base_rate) for l in loads if l.status in ["delivered", "completed"])
                total_loads = len([l for l in loads if l.status in ["delivered", "completed"]])

                # Calculate time period
                if loads:
                    first_load = min(l.created_at for l in loads if l.created_at)
                    last_load = max(l.created_at for l in loads if l.created_at)
                    months_active = max(1, (last_load - first_load).days / 30)
                else:
                    months_active = 1

                monthly_revenue = total_revenue / months_active if months_active > 0 else 0

                # Project 12-month LTV
                projected_ltv = monthly_revenue * 12

                return {
                    "status": "success",
                    "customer": customer_name,
                    "total_revenue": round(total_revenue, 2),
                    "total_loads": total_loads,
                    "months_active": round(months_active, 1),
                    "monthly_revenue": round(monthly_revenue, 2),
                    "projected_12month_ltv": round(projected_ltv, 2),
                }
            else:
                # Average LTV across all customers
                customer_revenues = {}
                for load in loads:
                    if load.status in ["delivered", "completed"]:
                        customer = load.customer_name
                        if customer not in customer_revenues:
                            customer_revenues[customer] = 0
                        customer_revenues[customer] += float(load.base_rate)

                total_customers = len(customer_revenues)
                total_revenue = sum(customer_revenues.values())
                avg_customer_value = total_revenue / total_customers if total_customers > 0 else 0

                return {
                    "status": "success",
                    "total_customers": total_customers,
                    "average_customer_ltv": round(avg_customer_value, 2),
                    "total_customer_value": round(total_revenue, 2),
                }

        except Exception as e:
            return {"error": str(e)}

    async def _generate_executive_summary(
        self,
        period: str = "month",
        **kwargs
    ) -> Dict[str, Any]:
        """Generate comprehensive executive summary."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Gather all key metrics
            kpis = await self._get_business_kpis(period=period, company_id=company_id)
            revenue_metrics = await self._calculate_revenue_metrics(period_days=30, company_id=company_id)
            forecast = await self._forecast_revenue(forecast_days=30, company_id=company_id)
            opportunities = await self._identify_growth_opportunities(company_id=company_id)

            # Build summary
            summary = {
                "status": "success",
                "period": period,
                "generated_at": datetime.utcnow().isoformat(),
                "highlights": {
                    "total_revenue": revenue_metrics.get("total_revenue", 0),
                    "growth_rate": revenue_metrics.get("growth_rate_percent", 0),
                    "total_loads": kpis.get("kpis", {}).get("total_loads", 0),
                    "unique_customers": kpis.get("kpis", {}).get("unique_customers", 0),
                },
                "forecast": {
                    "next_30_days_revenue": forecast.get("forecasted_revenue", 0),
                    "confidence": forecast.get("confidence", "medium"),
                },
                "growth_opportunities": {
                    "count": opportunities.get("opportunities_found", 0),
                    "top_opportunities": opportunities.get("opportunities", [])[:3],
                },
                "key_insights": [
                    f"Revenue growth: {revenue_metrics.get('growth_rate_percent', 0):.1f}%",
                    f"Active customers: {kpis.get('kpis', {}).get('unique_customers', 0)}",
                    f"Projected revenue (30 days): ${forecast.get('forecasted_revenue', 0):,.2f}",
                ],
            }

            return summary

        except Exception as e:
            return {"error": str(e)}
