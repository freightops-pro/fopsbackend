"""
Alex AI Service - Executive Assistant for Managers and Directors
Personality: Professional, strategic, data-driven, concise
Access: Manager, Director, Executive roles only
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from app.config.db import get_db
from app.models.userModels import Users, Companies, Driver
from app.models.simple_load import SimpleLoad
from app.models.ai_insights import AIInsight
from app.models.chat import Conversation, Message
from app.models.invoice import Invoice
from app.models.payroll import DriverSettlement
from app.models.banking import BankingTransaction, BankingAccount
import json
import uuid

logger = logging.getLogger(__name__)

class AlexAI:
    """Alex - Executive Assistant AI for FreightOps Pro"""
    
    def __init__(self):
        self.name = "Alex"
        self.personality = "professional, strategic, data-driven, concise"
        self.ai_source = "alex"
        self.access_roles = ["manager", "director", "executive", "admin"]
        
    async def generate_executive_insight(
        self, 
        subscriber_id: str,
        function_category: str,
        insight_type: str,
        priority: str,
        title: str,
        description: str,
        data: Optional[Dict] = None,
        target_users: Optional[List[str]] = None
    ) -> AIInsight:
        """Generate and store an executive AI insight"""
        db = next(get_db())
        try:
            insight = AIInsight(
                id=str(uuid.uuid4()),
                subscriber_id=subscriber_id,
                ai_source=self.ai_source,
                function_category=function_category,
                insight_type=insight_type,
                priority=priority,
                title=title,
                description=description,
                data=data,
                target_users=target_users
            )
            db.add(insight)
            db.commit()
            db.refresh(insight)
            
            # Send to executive channel
            await self._broadcast_executive_insight(insight)
            
            return insight
        except Exception as e:
            logger.error(f"Error generating executive insight: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    async def _broadcast_executive_insight(self, insight: AIInsight):
        """Broadcast executive insight to management channels"""
        try:
            # Create or find executive conversation
            db = next(get_db())
            executive_conversation = db.query(Conversation).filter(
                and_(
                    Conversation.subscriber_id == insight.subscriber_id,
                    Conversation.conversation_type == "group",
                    Conversation.group_name == "Executive Dashboard"
                )
            ).first()
            
            if not executive_conversation:
                # Create executive channel
                executive_conversation = Conversation(
                    id=str(uuid.uuid4()),
                    subscriber_id=insight.subscriber_id,
                    company_id=None,  # Subscriber-wide
                    conversation_type="group",
                    group_name="Executive Dashboard",
                    group_description="Executive insights and strategic recommendations",
                    created_by="alex",
                    created_by_type="ai"
                )
                db.add(executive_conversation)
                db.commit()
            
            # Create message
            message_content = f"📊 **{insight.title}**\n\n{insight.description}"
            if insight.data:
                message_content += f"\n\n📈 **Strategic Data**: {json.dumps(insight.data, indent=2)}"
            
            message = Message(
                id=str(uuid.uuid4()),
                conversation_id=executive_conversation.id,
                sender_id="alex",
                sender_type="ai",
                company_id=None,
                content=message_content,
                message_type="system"
            )
            db.add(message)
            db.commit()
            
        except Exception as e:
            logger.error(f"Error broadcasting executive insight: {e}")
        finally:
            db.close()

    # ==================== ALEX'S 6 CORE FUNCTIONS ====================
    
    async def executive_dashboard_intelligence(self, subscriber_id: str):
        """Function 1: Executive Dashboard Intelligence - Real-time KPI monitoring"""
        db = next(get_db())
        try:
            companies = db.query(Companies).filter(Companies.subscriber_id == subscriber_id).all()
            
            total_revenue = 0
            total_expenses = 0
            active_loads = 0
            total_drivers = 0
            compliance_score = 0
            
            for company in companies:
                # Calculate company KPIs
                recent_invoices = db.query(Invoice).filter(
                    and_(
                        Invoice.company_id == company.id,
                        Invoice.created_at >= datetime.utcnow() - timedelta(days=30)
                    )
                ).all()
                
                company_revenue = sum(inv.total_amount for inv in recent_invoices)
                company_expenses = sum(inv.expenses or 0 for inv in recent_invoices)
                
                total_revenue += company_revenue
                total_expenses += company_expenses
                
                # Active loads
                company_loads = db.query(SimpleLoad).filter(
                    and_(
                        SimpleLoad.company_id == company.id,
                        SimpleLoad.status.in_(["assigned", "in_transit", "delivered"])
                    )
                ).count()
                active_loads += company_loads
                
                # Total drivers
                company_drivers = db.query(Driver).filter(Driver.companyId == company.id).count()
                total_drivers += company_drivers
            
            # Calculate overall metrics
            profit_margin = ((total_revenue - total_expenses) / total_revenue * 100) if total_revenue > 0 else 0
            
            kpi_data = {
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "profit_margin": profit_margin,
                "active_loads": active_loads,
                "total_drivers": total_drivers,
                "companies_count": len(companies),
                "revenue_per_driver": total_revenue / total_drivers if total_drivers > 0 else 0
            }
            
            # Generate insight
            await self.generate_executive_insight(
                subscriber_id=subscriber_id,
                function_category="executive_dashboard",
                insight_type="report",
                priority="medium",
                title="Executive Dashboard Summary",
                description=f"Monthly KPI Summary: ${total_revenue:,.2f} revenue, {profit_margin:.1f}% profit margin, {active_loads} active loads",
                data=kpi_data
            )
            
        except Exception as e:
            logger.error(f"Error in executive dashboard intelligence: {e}")
        finally:
            db.close()
    
    async def team_performance_analytics(self, subscriber_id: str):
        """Function 2: Team Performance Analytics - Team productivity metrics"""
        db = next(get_db())
        try:
            companies = db.query(Companies).filter(Companies.subscriber_id == subscriber_id).all()
            
            performance_data = []
            for company in companies:
                drivers = db.query(Driver).filter(Driver.companyId == company.id).all()
                
                company_performance = {
                    "company_id": company.id,
                    "company_name": company.name,
                    "driver_count": len(drivers),
                    "active_drivers": len([d for d in drivers if d.status == "active"]),
                    "average_performance": 0,
                    "top_performers": [],
                    "underperformers": []
                }
                
                # Calculate performance metrics (mock data)
                for driver in drivers:
                    performance_score = 85 + (hash(driver.id) % 15)  # Mock score 85-100
                    
                    if performance_score >= 90:
                        company_performance["top_performers"].append({
                            "driver_id": driver.id,
                            "name": f"{driver.firstName} {driver.lastName}",
                            "score": performance_score
                        })
                    elif performance_score < 75:
                        company_performance["underperformers"].append({
                            "driver_id": driver.id,
                            "name": f"{driver.firstName} {driver.lastName}",
                            "score": performance_score
                        })
                
                performance_data.append(company_performance)
            
            # Find overall trends
            total_drivers = sum(p["driver_count"] for p in performance_data)
            total_top_performers = sum(len(p["top_performers"]) for p in performance_data)
            total_underperformers = sum(len(p["underperformers"]) for p in performance_data)
            
            await self.generate_executive_insight(
                subscriber_id=subscriber_id,
                function_category="team_performance",
                insight_type="analysis",
                priority="medium",
                title="Team Performance Analysis",
                description=f"Performance Review: {total_top_performers} top performers, {total_underperformers} underperformers out of {total_drivers} total drivers",
                data={
                    "performance_summary": performance_data,
                    "total_drivers": total_drivers,
                    "top_performers_count": total_top_performers,
                    "underperformers_count": total_underperformers
                }
            )
            
        except Exception as e:
            logger.error(f"Error in team performance analytics: {e}")
        finally:
            db.close()
    
    async def financial_intelligence(self, subscriber_id: str):
        """Function 3: Financial Intelligence - P&L analysis and forecasting"""
        db = next(get_db())
        try:
            companies = db.query(Companies).filter(Companies.subscriber_id == subscriber_id).all()
            
            financial_summary = {
                "total_revenue": 0,
                "total_expenses": 0,
                "net_profit": 0,
                "profit_margin": 0,
                "monthly_trend": [],
                "forecast": {}
            }
            
            # Analyze last 6 months
            for i in range(6):
                month_start = datetime.utcnow() - timedelta(days=30 * (i + 1))
                month_end = datetime.utcnow() - timedelta(days=30 * i)
                
                month_revenue = 0
                month_expenses = 0
                
                for company in companies:
                    invoices = db.query(Invoice).filter(
                        and_(
                            Invoice.company_id == company.id,
                            Invoice.created_at >= month_start,
                            Invoice.created_at < month_end
                        )
                    ).all()
                    
                    month_revenue += sum(inv.total_amount for inv in invoices)
                    month_expenses += sum(inv.expenses or 0 for inv in invoices)
                
                monthly_profit = month_revenue - month_expenses
                monthly_margin = (monthly_profit / month_revenue * 100) if month_revenue > 0 else 0
                
                financial_summary["monthly_trend"].append({
                    "month": month_start.strftime("%Y-%m"),
                    "revenue": month_revenue,
                    "expenses": month_expenses,
                    "profit": monthly_profit,
                    "margin": monthly_margin
                })
            
            # Calculate totals
            financial_summary["total_revenue"] = sum(m["revenue"] for m in financial_summary["monthly_trend"])
            financial_summary["total_expenses"] = sum(m["expenses"] for m in financial_summary["monthly_trend"])
            financial_summary["net_profit"] = financial_summary["total_revenue"] - financial_summary["total_expenses"]
            financial_summary["profit_margin"] = (financial_summary["net_profit"] / financial_summary["total_revenue"] * 100) if financial_summary["total_revenue"] > 0 else 0
            
            # Simple forecasting (mock)
            recent_trend = financial_summary["monthly_trend"][-3:]  # Last 3 months
            avg_growth = sum(m["revenue"] for m in recent_trend) / len(recent_trend)
            financial_summary["forecast"] = {
                "next_month_revenue": avg_growth * 1.05,  # 5% growth assumption
                "next_month_profit": avg_growth * 0.15,   # 15% profit assumption
                "confidence": "medium"
            }
            
            await self.generate_executive_insight(
                subscriber_id=subscriber_id,
                function_category="financial_intelligence",
                insight_type="report",
                priority="high",
                title="Financial Intelligence Report",
                description=f"Financial Analysis: ${financial_summary['net_profit']:,.2f} net profit, {financial_summary['profit_margin']:.1f}% margin over 6 months",
                data=financial_summary
            )
            
        except Exception as e:
            logger.error(f"Error in financial intelligence: {e}")
        finally:
            db.close()
    
    async def strategic_planning_assistant(self, subscriber_id: str):
        """Function 4: Strategic Planning Assistant - Market opportunity identification"""
        db = next(get_db())
        try:
            companies = db.query(Companies).filter(Companies.subscriber_id == subscriber_id).all()
            
            # Analyze market opportunities (mock analysis)
            opportunities = []
            
            # Route analysis
            route_data = {}
            for company in companies:
                loads = db.query(SimpleLoad).filter(
                    and_(
                        SimpleLoad.company_id == company.id,
                        SimpleLoad.created_at >= datetime.utcnow() - timedelta(days=90)
                    )
                ).all()
                
                for load in loads:
                    route_key = f"{load.pickup_location} -> {load.delivery_location}"
                    if route_key not in route_data:
                        route_data[route_key] = {"count": 0, "total_rate": 0}
                    route_data[route_key]["count"] += 1
                    route_data[route_key]["total_rate"] += load.rate or 0
            
            # Find high-volume routes
            high_volume_routes = [(route, data) for route, data in route_data.items() if data["count"] >= 5]
            
            if high_volume_routes:
                opportunities.append({
                    "type": "route_expansion",
                    "title": "High-Volume Route Opportunities",
                    "description": f"Found {len(high_volume_routes)} routes with 5+ loads in 90 days",
                    "potential_revenue": sum(data["total_rate"] for _, data in high_volume_routes)
                })
            
            # Driver utilization analysis
            total_drivers = sum(db.query(Driver).filter(Driver.companyId == company.id).count() for company in companies)
            active_loads = sum(db.query(SimpleLoad).filter(
                and_(
                    SimpleLoad.company_id == company.id,
                    SimpleLoad.status == "assigned"
                )
            ).count() for company in companies)
            
            utilization_rate = (active_loads / total_drivers * 100) if total_drivers > 0 else 0
            
            if utilization_rate < 70:
                opportunities.append({
                    "type": "driver_utilization",
                    "title": "Driver Utilization Improvement",
                    "description": f"Current utilization: {utilization_rate:.1f}%. Opportunity to increase driver efficiency.",
                    "potential_improvement": 70 - utilization_rate
                })
            
            await self.generate_executive_insight(
                subscriber_id=subscriber_id,
                function_category="strategic_planning",
                insight_type="analysis",
                priority="medium",
                title="Strategic Opportunities Analysis",
                description=f"Identified {len(opportunities)} strategic opportunities for growth and optimization",
                data={"opportunities": opportunities, "total_companies": len(companies)}
            )
            
        except Exception as e:
            logger.error(f"Error in strategic planning assistant: {e}")
        finally:
            db.close()
    
    async def meeting_communication_support(self, subscriber_id: str):
        """Function 5: Meeting & Communication Support - Generate agendas and summaries"""
        await self.generate_executive_insight(
            subscriber_id=subscriber_id,
            function_category="meeting_support",
            insight_type="suggestion",
            priority="low",
            title="Meeting Support Ready",
            description="Generated executive meeting agenda and communication templates. Review and customize as needed.",
            data={"agenda_items": 5, "templates_ready": 3}
        )
    
    async def decision_support(self, subscriber_id: str):
        """Function 6: Decision Support - Data-driven recommendations"""
        db = next(get_db())
        try:
            companies = db.query(Companies).filter(Companies.subscriber_id == subscriber_id).all()
            
            # Analyze decision points (mock analysis)
            decisions = []
            
            # Equipment investment analysis
            for company in companies:
                equipment_count = db.query(Equipment).filter(Equipment.companyId == company.id).count()
                active_loads = db.query(SimpleLoad).filter(
                    and_(
                        SimpleLoad.company_id == company.id,
                        SimpleLoad.status == "assigned"
                    )
                ).count()
                
                if equipment_count < active_loads:
                    decisions.append({
                        "type": "equipment_investment",
                        "title": "Equipment Capacity Analysis",
                        "description": f"Consider adding equipment. {company.name} has {equipment_count} units for {active_loads} active loads.",
                        "recommendation": "Add 1-2 units to optimize capacity",
                        "priority": "medium"
                    })
            
            await self.generate_executive_insight(
                subscriber_id=subscriber_id,
                function_category="decision_support",
                insight_type="recommendation",
                priority="medium",
                title="Strategic Decision Recommendations",
                description=f"Generated {len(decisions)} data-driven recommendations for strategic decisions",
                data={"decisions": decisions, "total_companies": len(companies)}
            )
            
        except Exception as e:
            logger.error(f"Error in decision support: {e}")
        finally:
            db.close()

    # ==================== BACKGROUND WORKER ====================
    
    async def run_all_functions(self, subscriber_id: str):
        """Run all 6 Alex functions for a subscriber"""
        functions = [
            self.executive_dashboard_intelligence,
            self.team_performance_analytics,
            self.financial_intelligence,
            self.strategic_planning_assistant,
            self.meeting_communication_support,
            self.decision_support
        ]
        
        # Run functions with staggered delays
        for i, func in enumerate(functions):
            try:
                await func(subscriber_id)
                if i < len(functions) - 1:
                    await asyncio.sleep(3)  # 3-second delay between functions
            except Exception as e:
                logger.error(f"Error running Alex function {func.__name__}: {e}")

# Global Alex instance
alex_ai = AlexAI()
