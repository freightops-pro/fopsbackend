"""
Atlas AI API Routes - HQ Admin AI for FreightOps SaaS Administrators
Access: FreightOps HQ team only (hq_admin, super_admin, system_admin roles)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.config.db import get_db
from app.models.ai_insights import AIInsight
from app.models.userModels import Users, Companies
from app.models.chat import Conversation, Message
from app.models.hqModels import HQAdmin
from app.services.atlas_ai import atlas_ai
from app.routes.user import get_current_user
import uuid

router = APIRouter(prefix="/api/atlas", tags=["Atlas AI"])

def check_hq_admin_access(user: Users):
    """Check if user has HQ admin access"""
    hq_admin_roles = ["hq_admin", "super_admin", "system_admin"]
    if user.role.lower() not in hq_admin_roles:
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Atlas AI is only available for HQ administrators."
        )

@router.get("/insights")
async def get_atlas_insights(
    function_category: Optional[str] = Query(None, description="Filter by function category"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    status: Optional[str] = Query("pending", description="Filter by status"),
    limit: int = Query(50, description="Number of insights to return"),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Atlas's HQ admin insights"""
    check_hq_admin_access(current_user)
    
    try:
        query = db.query(AIInsight).filter(AIInsight.ai_source == "atlas")
        
        # Apply filters
        if function_category:
            query = query.filter(AIInsight.function_category == function_category)
        if priority:
            query = query.filter(AIInsight.priority == priority)
        if status:
            query = query.filter(AIInsight.status == status)
        
        # Get insights
        insights = query.order_by(AIInsight.created_at.desc()).limit(limit).all()
        
        return {"insights": insights, "count": len(insights)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Atlas insights: {str(e)}")

@router.post("/insights/{insight_id}/dismiss")
async def dismiss_atlas_insight(
    insight_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dismiss an Atlas insight"""
    check_hq_admin_access(current_user)
    
    try:
        insight = db.query(AIInsight).filter(
            AIInsight.id == insight_id,
            AIInsight.ai_source == "atlas"
        ).first()
        
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        insight.status = "dismissed"
        insight.dismissed_by = current_user.id
        db.commit()
        
        return {"message": "Atlas insight dismissed successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error dismissing Atlas insight: {str(e)}")

@router.post("/chat")
async def chat_with_atlas(
    message: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat with Atlas AI HQ admin assistant"""
    check_hq_admin_access(current_user)
    
    try:
        # Create or find HQ admin AI conversation
        ai_conversation = db.query(Conversation).filter(
            Conversation.ai_source == "atlas",
            Conversation.is_ai_conversation == True,
            Conversation.participant1_id == current_user.id
        ).first()
        
        if not ai_conversation:
            ai_conversation = Conversation(
                id=str(uuid.uuid4()),
                subscriber_id=None,  # HQ-wide conversation
                company_id=None,
                conversation_type="ai_conversation",
                ai_source="atlas",
                is_ai_conversation=True,
                participant1_id=current_user.id,
                participant1_type="user",
                participant2_id="atlas",
                participant2_type="ai",
                created_by=current_user.id,
                created_by_type="user"
            )
            db.add(ai_conversation)
            db.commit()
        
        # Save user message
        user_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=ai_conversation.id,
            sender_id=current_user.id,
            sender_type="user",
            company_id=None,
            content=message
        )
        db.add(user_message)
        
        # Generate Atlas's response (mock for now - would integrate with LLM)
        atlas_response = f"HQ Analysis: Based on your query '{message}', here's my system-level assessment with technical insights and administrative recommendations..."
        
        # Save Atlas's response
        atlas_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=ai_conversation.id,
            sender_id="atlas",
            sender_type="ai",
            company_id=None,
            content=atlas_response
        )
        db.add(atlas_message)
        
        db.commit()
        
        return {
            "conversation_id": ai_conversation.id,
            "user_message": user_message,
            "atlas_response": atlas_message
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error chatting with Atlas: {str(e)}")

@router.get("/platform-health")
async def get_platform_health(
    current_user: Users = Depends(get_current_user)
):
    """Get real-time platform health metrics"""
    check_hq_admin_access(current_user)
    
    try:
        import psutil
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        health_metrics = {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "status": "healthy" if cpu_percent < 80 and memory.percent < 85 and disk.percent < 90 else "warning",
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        return {"platform_health": health_metrics}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching platform health: {str(e)}")

@router.get("/subscribers")
async def get_subscriber_analytics(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get subscriber analytics and health scores"""
    check_hq_admin_access(current_user)
    
    try:
        # Get all subscribers
        companies = db.query(Companies).filter(
            Companies.subscriber_id.isnot(None)
        ).distinct(Companies.subscriber_id).all()
        
        subscriber_analytics = []
        for company in companies:
            if not company.subscriber_id:
                continue
                
            # Calculate metrics
            user_count = db.query(Users).filter(Users.companyid == company.id).count()
            
            subscriber_analytics.append({
                "subscriber_id": company.subscriber_id,
                "company_name": company.name,
                "user_count": user_count,
                "subscription_status": company.subscriptionStatus,
                "subscription_plan": company.subscriptionPlan,
                "health_score": 85 + (hash(company.subscriber_id) % 15),  # Mock score
                "created_at": company.createdAt.isoformat() if company.createdAt else None
            })
        
        return {"subscriber_analytics": subscriber_analytics, "total_subscribers": len(subscriber_analytics)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching subscriber analytics: {str(e)}")

@router.get("/support-tickets")
async def get_support_ticket_analysis(
    current_user: Users = Depends(get_current_user)
):
    """Get support ticket analysis and categorization"""
    check_hq_admin_access(current_user)
    
    try:
        # Mock support ticket data
        support_analysis = {
            "total_tickets": 45,
            "open_tickets": 12,
            "high_priority_tickets": 3,
            "tickets_by_category": {
                "technical": 15,
                "billing": 8,
                "feature_request": 12,
                "bug_report": 6,
                "general": 4
            },
            "average_resolution_time": "2.3 hours",
            "customer_satisfaction": 4.2
        }
        
        return {"support_analysis": support_analysis}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching support analysis: {str(e)}")

@router.get("/security-audit")
async def get_security_audit_report(
    current_user: Users = Depends(get_current_user)
):
    """Get security audit report"""
    check_hq_admin_access(current_user)
    
    try:
        # Mock security audit data
        security_report = {
            "total_security_events": 67,
            "high_severity_events": 3,
            "medium_severity_events": 12,
            "low_severity_events": 52,
            "events_by_type": {
                "failed_login": 45,
                "suspicious_activity": 8,
                "data_access": 12,
                "api_abuse": 2
            },
            "security_score": 92,
            "last_audit": "2024-01-15T08:00:00Z"
        }
        
        return {"security_report": security_report}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching security audit: {str(e)}")

# Function-specific endpoints for Atlas's 8 functions

@router.post("/platform-health/monitor")
async def monitor_platform_health(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Atlas's platform health monitoring"""
    check_hq_admin_access(current_user)
    
    try:
        await atlas_ai.platform_health_monitoring("hq_global")  # Global HQ subscriber
        return {"message": "Platform health monitoring triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering platform health monitoring: {str(e)}")

@router.post("/subscribers/analyze")
async def analyze_subscriber_management(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Atlas's subscriber management analysis"""
    check_hq_admin_access(current_user)
    
    try:
        await atlas_ai.subscriber_management_intelligence("hq_global")
        return {"message": "Subscriber management analysis triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering subscriber management analysis: {str(e)}")

@router.post("/support/analyze")
async def analyze_support_automation(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Atlas's support automation analysis"""
    check_hq_admin_access(current_user)
    
    try:
        await atlas_ai.support_automation("hq_global")
        return {"message": "Support automation analysis triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering support automation analysis: {str(e)}")

@router.post("/security/audit")
async def audit_security_compliance(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Atlas's security compliance audit"""
    check_hq_admin_access(current_user)
    
    try:
        await atlas_ai.security_compliance("hq_global")
        return {"message": "Security compliance audit triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering security compliance audit: {str(e)}")

@router.post("/business/analyze")
async def analyze_business_intelligence(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Atlas's business intelligence analysis"""
    check_hq_admin_access(current_user)
    
    try:
        await atlas_ai.business_intelligence("hq_global")
        return {"message": "Business intelligence analysis triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering business intelligence analysis: {str(e)}")

@router.post("/run-all-functions")
async def run_all_atlas_functions(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger all 8 Atlas functions"""
    check_hq_admin_access(current_user)
    
    try:
        await atlas_ai.run_all_functions("hq_global")
        return {"message": "All Atlas functions triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering Atlas functions: {str(e)}")

@router.get("/functions")
async def get_atlas_functions():
    """Get list of Atlas's 8 functions"""
    functions = [
        {
            "id": "platform_health_monitoring",
            "name": "Platform Health Monitoring",
            "description": "Real-time system performance and resource monitoring",
            "category": "platform_health"
        },
        {
            "id": "subscriber_management_intelligence",
            "name": "Subscriber Management Intelligence",
            "description": "Subscriber health scores and churn risk prediction",
            "category": "subscriber_management"
        },
        {
            "id": "support_automation",
            "name": "Support Automation",
            "description": "Categorize support tickets and suggest solutions",
            "category": "support_automation"
        },
        {
            "id": "security_compliance",
            "name": "Security & Compliance",
            "description": "Monitor security threats and compliance violations",
            "category": "security_compliance"
        },
        {
            "id": "business_intelligence",
            "name": "Business Intelligence",
            "description": "MRR/ARR tracking and revenue forecasting",
            "category": "business_intelligence"
        },
        {
            "id": "system_optimization",
            "name": "System Optimization",
            "description": "Performance recommendations and optimization",
            "category": "system_optimization"
        },
        {
            "id": "onboarding_activation",
            "name": "Onboarding & Activation",
            "description": "Track onboarding progress and identify blockers",
            "category": "onboarding_activation"
        },
        {
            "id": "proactive_maintenance",
            "name": "Proactive Maintenance",
            "description": "Predict outages and recommend maintenance",
            "category": "proactive_maintenance"
        }
    ]
    
    return {"functions": functions, "total_count": len(functions)}
