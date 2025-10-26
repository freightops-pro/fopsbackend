"""
Atlas AI Service - HQ Admin AI for FreightOps SaaS Administrators
Personality: Analytical, system-focused, security-conscious
Access: FreightOps HQ team only
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from app.config.db import get_db
from app.models.userModels import Users, Companies
from app.models.ai_insights import AIInsight
from app.models.chat import Conversation, Message
from app.models.stripeModels import CompanySubscription
import json
import uuid
import psutil
import os

logger = logging.getLogger(__name__)

class AtlasAI:
    """Atlas - HQ Admin AI for FreightOps Pro"""
    
    def __init__(self):
        self.name = "Atlas"
        self.personality = "analytical, system-focused, security-conscious"
        self.ai_source = "atlas"
        self.access_roles = ["hq_admin", "super_admin", "system_admin"]
        
    async def generate_hq_insight(
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
        """Generate and store an HQ admin AI insight"""
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
            
            # Send to HQ admin channel
            await self._broadcast_hq_insight(insight)
            
            return insight
        except Exception as e:
            logger.error(f"Error generating HQ insight: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    async def _broadcast_hq_insight(self, insight: AIInsight):
        """Broadcast HQ insight to admin channels"""
        try:
            # Create or find HQ admin conversation
            db = next(get_db())
            hq_conversation = db.query(Conversation).filter(
                and_(
                    Conversation.subscriber_id == insight.subscriber_id,
                    Conversation.conversation_type == "group",
                    Conversation.group_name == "HQ Admin Dashboard"
                )
            ).first()
            
            if not hq_conversation:
                # Create HQ admin channel
                hq_conversation = Conversation(
                    id=str(uuid.uuid4()),
                    subscriber_id=insight.subscriber_id,
                    company_id=None,  # Subscriber-wide
                    conversation_type="group",
                    group_name="HQ Admin Dashboard",
                    group_description="HQ administrative insights and system monitoring",
                    created_by="atlas",
                    created_by_type="ai"
                )
                db.add(hq_conversation)
                db.commit()
            
            # Create message
            message_content = f"🔧 **{insight.title}**\n\n{insight.description}"
            if insight.data:
                message_content += f"\n\n📊 **System Data**: {json.dumps(insight.data, indent=2)}"
            
            message = Message(
                id=str(uuid.uuid4()),
                conversation_id=hq_conversation.id,
                sender_id="atlas",
                sender_type="ai",
                company_id=None,
                content=message_content,
                message_type="system"
            )
            db.add(message)
            db.commit()
            
        except Exception as e:
            logger.error(f"Error broadcasting HQ insight: {e}")
        finally:
            db.close()

    # ==================== ATLAS'S 8 CORE FUNCTIONS ====================
    
    async def platform_health_monitoring(self, subscriber_id: str):
        """Function 1: Platform Health Monitoring - Real-time system performance"""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Database performance (mock)
            db = next(get_db())
            try:
                # Simple query to test DB performance
                db.query(Companies).first()
                db_performance = "healthy"
            except Exception as e:
                db_performance = f"error: {str(e)}"
            finally:
                db.close()
            
            system_metrics = {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "disk_usage": disk.percent,
                "database_status": db_performance,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Determine health status
            health_status = "healthy"
            if cpu_percent > 80 or memory.percent > 85 or disk.percent > 90:
                health_status = "warning"
            if cpu_percent > 95 or memory.percent > 95 or disk.percent > 95:
                health_status = "critical"
            
            await self.generate_hq_insight(
                subscriber_id=subscriber_id,
                function_category="platform_health",
                insight_type="report",
                priority="medium" if health_status == "healthy" else "high",
                title=f"Platform Health Status: {health_status.title()}",
                description=f"System metrics: CPU {cpu_percent}%, Memory {memory.percent}%, Disk {disk.percent}%",
                data=system_metrics
            )
            
        except Exception as e:
            logger.error(f"Error in platform health monitoring: {e}")
    
    async def subscriber_management_intelligence(self, subscriber_id: str):
        """Function 2: Subscriber Management Intelligence - Subscriber health scores"""
        db = next(get_db())
        try:
            # Get all subscribers
            all_subscribers = db.query(Companies).filter(
                Companies.subscriber_id.isnot(None)
            ).distinct(Companies.subscriber_id).all()
            
            subscriber_health = []
            for company in all_subscribers:
                if not company.subscriber_id:
                    continue
                    
                # Calculate health metrics
                user_count = db.query(Users).filter(Users.companyid == company.id).count()
                subscription_status = company.subscriptionStatus or "trial"
                subscription_plan = company.subscriptionPlan or "starter"
                
                # Mock health score calculation
                health_score = 85 + (hash(company.subscriber_id) % 15)  # 85-100
                
                # Determine churn risk
                churn_risk = "low"
                if subscription_status == "trial" and user_count < 2:
                    churn_risk = "high"
                elif subscription_status == "active" and health_score < 80:
                    churn_risk = "medium"
                
                subscriber_health.append({
                    "subscriber_id": company.subscriber_id,
                    "company_name": company.name,
                    "user_count": user_count,
                    "subscription_status": subscription_status,
                    "subscription_plan": subscription_plan,
                    "health_score": health_score,
                    "churn_risk": churn_risk
                })
            
            # Find high-risk subscribers
            high_risk_subscribers = [s for s in subscriber_health if s["churn_risk"] in ["high", "medium"]]
            
            if high_risk_subscribers:
                await self.generate_hq_insight(
                    subscriber_id=subscriber_id,
                    function_category="subscriber_management",
                    insight_type="alert",
                    priority="high",
                    title="Subscriber Churn Risk Alert",
                    description=f"Found {len(high_risk_subscribers)} subscribers at risk of churning",
                    data={"high_risk_subscribers": high_risk_subscribers, "total_subscribers": len(subscriber_health)}
                )
            
        except Exception as e:
            logger.error(f"Error in subscriber management intelligence: {e}")
        finally:
            db.close()
    
    async def support_automation(self, subscriber_id: str):
        """Function 3: Support Automation - Categorize support tickets"""
        # Mock support ticket analysis
        support_tickets = [
            {"id": "TICKET-001", "category": "technical", "priority": "high", "status": "open"},
            {"id": "TICKET-002", "category": "billing", "priority": "medium", "status": "open"},
            {"id": "TICKET-003", "category": "feature_request", "priority": "low", "status": "open"}
        ]
        
        open_tickets = [t for t in support_tickets if t["status"] == "open"]
        high_priority_tickets = [t for t in open_tickets if t["priority"] == "high"]
        
        await self.generate_hq_insight(
            subscriber_id=subscriber_id,
            function_category="support_automation",
            insight_type="report",
            priority="medium",
            title="Support Ticket Analysis",
            description=f"Open tickets: {len(open_tickets)}, High priority: {len(high_priority_tickets)}",
            data={"support_tickets": support_tickets, "summary": {"open": len(open_tickets), "high_priority": len(high_priority_tickets)}}
        )
    
    async def security_compliance(self, subscriber_id: str):
        """Function 4: Security & Compliance - Monitor security threats"""
        # Mock security analysis
        security_events = [
            {"type": "failed_login", "count": 15, "severity": "medium"},
            {"type": "suspicious_activity", "count": 2, "severity": "high"},
            {"type": "data_access", "count": 45, "severity": "low"}
        ]
        
        high_severity_events = [e for e in security_events if e["severity"] == "high"]
        
        if high_severity_events:
            await self.generate_hq_insight(
                subscriber_id=subscriber_id,
                function_category="security_compliance",
                insight_type="alert",
                priority="high",
                title="Security Alert",
                description=f"Detected {len(high_severity_events)} high-severity security events",
                data={"security_events": security_events, "high_severity_count": len(high_severity_events)}
            )
    
    async def business_intelligence(self, subscriber_id: str):
        """Function 5: Business Intelligence - MRR/ARR tracking"""
        db = next(get_db())
        try:
            # Calculate MRR/ARR (mock calculation)
            subscriptions = db.query(CompanySubscription).filter(
                CompanySubscription.status == "active"
            ).all()
            
            total_mrr = sum(sub.price_amount for sub in subscriptions if sub.price_amount)
            total_arr = total_mrr * 12
            
            # Customer metrics
            total_customers = len(subscriptions)
            new_customers_this_month = len([s for s in subscriptions if s.created_at and s.created_at >= datetime.utcnow() - timedelta(days=30)])
            
            business_metrics = {
                "total_mrr": total_mrr,
                "total_arr": total_arr,
                "total_customers": total_customers,
                "new_customers_this_month": new_customers_this_month,
                "average_revenue_per_customer": total_mrr / total_customers if total_customers > 0 else 0
            }
            
            await self.generate_hq_insight(
                subscriber_id=subscriber_id,
                function_category="business_intelligence",
                insight_type="report",
                priority="medium",
                title="Business Intelligence Report",
                description=f"MRR: ${total_mrr:,.2f}, ARR: ${total_arr:,.2f}, Customers: {total_customers}",
                data=business_metrics
            )
            
        except Exception as e:
            logger.error(f"Error in business intelligence: {e}")
        finally:
            db.close()
    
    async def system_optimization(self, subscriber_id: str):
        """Function 6: System Optimization - Performance recommendations"""
        # Mock system optimization analysis
        optimization_opportunities = [
            {"type": "database_query", "description": "Optimize slow queries in load management", "impact": "high"},
            {"type": "caching", "description": "Implement Redis caching for frequent lookups", "impact": "medium"},
            {"type": "indexing", "description": "Add database indexes for better performance", "impact": "medium"}
        ]
        
        await self.generate_hq_insight(
            subscriber_id=subscriber_id,
            function_category="system_optimization",
            insight_type="recommendation",
            priority="medium",
            title="System Optimization Recommendations",
            description=f"Identified {len(optimization_opportunities)} optimization opportunities",
            data={"optimization_opportunities": optimization_opportunities}
        )
    
    async def onboarding_activation(self, subscriber_id: str):
        """Function 7: Onboarding & Activation - Track onboarding progress"""
        # Mock onboarding analysis
        onboarding_stats = {
            "total_signups": 150,
            "completed_onboarding": 120,
            "stalled_onboardings": 30,
            "average_completion_time": "3.2 days"
        }
        
        if onboarding_stats["stalled_onboardings"] > 20:
            await self.generate_hq_insight(
                subscriber_id=subscriber_id,
                function_category="onboarding_activation",
                insight_type="alert",
                priority="medium",
                title="Onboarding Activation Alert",
                description=f"High number of stalled onboardings: {onboarding_stats['stalled_onboardings']}",
                data=onboarding_stats
            )
    
    async def proactive_maintenance(self, subscriber_id: str):
        """Function 8: Proactive Maintenance - Predict and prevent outages"""
        # Mock maintenance analysis
        maintenance_alerts = [
            {"component": "database", "status": "warning", "message": "High connection count detected"},
            {"component": "storage", "status": "info", "message": "Storage usage at 75%"},
            {"component": "api", "status": "healthy", "message": "All APIs responding normally"}
        ]
        
        warning_alerts = [a for a in maintenance_alerts if a["status"] == "warning"]
        
        if warning_alerts:
            await self.generate_hq_insight(
                subscriber_id=subscriber_id,
                function_category="proactive_maintenance",
                insight_type="alert",
                priority="high",
                title="Proactive Maintenance Alert",
                description=f"System warnings detected: {len(warning_alerts)} components need attention",
                data={"maintenance_alerts": maintenance_alerts, "warning_count": len(warning_alerts)}
            )

    # ==================== BACKGROUND WORKER ====================
    
    async def run_all_functions(self, subscriber_id: str):
        """Run all 8 Atlas functions for a subscriber"""
        functions = [
            self.platform_health_monitoring,
            self.subscriber_management_intelligence,
            self.support_automation,
            self.security_compliance,
            self.business_intelligence,
            self.system_optimization,
            self.onboarding_activation,
            self.proactive_maintenance
        ]
        
        # Run functions with staggered delays
        for i, func in enumerate(functions):
            try:
                await func(subscriber_id)
                if i < len(functions) - 1:
                    await asyncio.sleep(2)  # 2-second delay between functions
            except Exception as e:
                logger.error(f"Error running Atlas function {func.__name__}: {e}")

# Global Atlas instance
atlas_ai = AtlasAI()
