"""
Annie AI API Routes - Operational AI Assistant for all users
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.config.db import get_db
from app.models.ai_insights import AIInsight
from app.models.userModels import Users, Companies
from app.models.chat import Conversation, Message
from app.services.annie_ai import annie_ai
from app.schema.ai_insights import AIInsightResponse, AIInsightCreate
from app.routes.user import get_current_user
import uuid
import json

router = APIRouter(prefix="/api/annie", tags=["Annie AI"])

@router.get("/insights")
async def get_annie_insights(
    function_category: Optional[str] = Query(None, description="Filter by function category"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    status: Optional[str] = Query("pending", description="Filter by status"),
    limit: int = Query(50, description="Number of insights to return"),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Annie's insights for the user's subscriber"""
    try:
        # Get user's company and subscriber
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        query = db.query(AIInsight).filter(AIInsight.subscriber_id == company.subscriber_id)
        
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
        raise HTTPException(status_code=500, detail=f"Error fetching insights: {str(e)}")

@router.post("/insights/{insight_id}/dismiss")
async def dismiss_insight(
    insight_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dismiss an Annie insight"""
    try:
        # Get user's company and subscriber
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        insight = db.query(AIInsight).filter(
            AIInsight.id == insight_id,
            AIInsight.subscriber_id == company.subscriber_id
        ).first()
        
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        insight.status = "dismissed"
        insight.dismissed_by = current_user.id
        db.commit()
        
        return {"message": "Insight dismissed successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error dismissing insight: {str(e)}")

@router.post("/insights/{insight_id}/accept")
async def accept_insight(
    insight_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept an Annie insight"""
    try:
        # Get user's company and subscriber
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        insight = db.query(AIInsight).filter(
            AIInsight.id == insight_id,
            AIInsight.subscriber_id == company.subscriber_id
        ).first()
        
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        insight.status = "accepted"
        db.commit()
        
        return {"message": "Insight accepted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accepting insight: {str(e)}")

@router.post("/chat")
async def chat_with_annie(
    message: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat with Annie AI assistant"""
    try:
        # Get user's company and subscriber
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        # Create or find AI conversation
        ai_conversation = db.query(Conversation).filter(
            Conversation.subscriber_id == company.subscriber_id,
            Conversation.ai_source == "annie",
            Conversation.is_ai_conversation == True,
            Conversation.participant1_id == current_user.id
        ).first()
        
        if not ai_conversation:
            ai_conversation = Conversation(
                id=str(uuid.uuid4()),
                subscriber_id=company.subscriber_id,
                company_id=company.id,
                conversation_type="ai_conversation",
                ai_source="annie",
                is_ai_conversation=True,
                participant1_id=current_user.id,
                participant1_type="user",
                participant2_id="annie",
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
            company_id=company.id,
            content=message
        )
        db.add(user_message)
        
        # Generate Annie's response (mock for now - would integrate with LLM)
        annie_response = f"Hi {current_user.firstname}! 😊 I understand you're asking about '{message}'. Let me help you with that! Based on my analysis of your company's data, here's what I found..."
        
        # Save Annie's response
        annie_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=ai_conversation.id,
            sender_id="annie",
            sender_type="ai",
            company_id=company.id,
            content=annie_response
        )
        db.add(annie_message)
        
        db.commit()
        
        return {
            "conversation_id": ai_conversation.id,
            "user_message": user_message,
            "annie_response": annie_message
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error chatting with Annie: {str(e)}")

@router.get("/chat/history")
async def get_chat_history(
    limit: int = Query(20, description="Number of messages to return"),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history with Annie"""
    try:
        # Get user's company and subscriber
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        # Get AI conversation
        ai_conversation = db.query(Conversation).filter(
            Conversation.subscriber_id == company.subscriber_id,
            Conversation.ai_source == "annie",
            Conversation.is_ai_conversation == True,
            Conversation.participant1_id == current_user.id
        ).first()
        
        if not ai_conversation:
            return {"messages": [], "conversation_id": None}
        
        # Get messages
        messages = db.query(Message).filter(
            Message.conversation_id == ai_conversation.id
        ).order_by(Message.created_at.desc()).limit(limit).all()
        
        return {
            "messages": list(reversed(messages)),  # Return in chronological order
            "conversation_id": ai_conversation.id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chat history: {str(e)}")

# Function-specific endpoints for Annie's 18 functions

@router.post("/accounting/analyze")
async def analyze_accounting(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Annie's accounting analysis"""
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await annie_ai.accounting_assistant(company.subscriber_id)
        return {"message": "Accounting analysis triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering accounting analysis: {str(e)}")

@router.post("/payroll/validate")
async def validate_payroll(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Annie's payroll validation"""
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await annie_ai.payroll_manager(company.subscriber_id)
        return {"message": "Payroll validation triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering payroll validation: {str(e)}")

@router.post("/dispatch/suggest-matches")
async def suggest_dispatch_matches(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Annie's dispatch matching suggestions"""
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await annie_ai.dispatch_coordinator(company.subscriber_id)
        return {"message": "Dispatch matching suggestions triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering dispatch suggestions: {str(e)}")

@router.post("/safety/audit-compliance")
async def audit_safety_compliance(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Annie's safety compliance audit"""
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await annie_ai.safety_compliance_auditor(company.subscriber_id)
        return {"message": "Safety compliance audit triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering safety audit: {str(e)}")

@router.post("/banking/analyze-cash-flow")
async def analyze_cash_flow(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Annie's banking cash flow analysis"""
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await annie_ai.banking_cash_flow_assistant(company.subscriber_id)
        return {"message": "Cash flow analysis triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering cash flow analysis: {str(e)}")

@router.post("/loadboard/suggest-rates")
async def suggest_loadboard_rates(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Annie's load board rate intelligence"""
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await annie_ai.load_board_rate_intelligence(company.subscriber_id)
        return {"message": "Load board rate suggestions triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering rate suggestions: {str(e)}")

@router.post("/run-all-functions")
async def run_all_annie_functions(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger all 18 Annie functions for the user's subscriber"""
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await annie_ai.run_all_functions(company.subscriber_id)
        return {"message": "All Annie functions triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering Annie functions: {str(e)}")

@router.get("/functions")
async def get_annie_functions():
    """Get list of Annie's 18 functions"""
    functions = [
        {
            "id": "accounting_assistant",
            "name": "Accounting Assistant",
            "description": "Auto-process invoices and expenses, calculate profit/loss margins",
            "category": "accounting"
        },
        {
            "id": "payroll_manager",
            "name": "Payroll Manager",
            "description": "Validate driver timesheets and calculate settlements",
            "category": "payroll"
        },
        {
            "id": "dispatch_coordinator",
            "name": "Dispatch Coordinator",
            "description": "Match drivers to loads (suggest only)",
            "category": "dispatch"
        },
        {
            "id": "safety_compliance_auditor",
            "name": "Safety & Compliance Auditor",
            "description": "Audit ELD logs and track compliance violations",
            "category": "safety"
        },
        {
            "id": "banking_cash_flow_assistant",
            "name": "Banking & Cash Flow Assistant",
            "description": "Monitor account balances and predict cash shortfalls",
            "category": "banking"
        },
        {
            "id": "load_board_rate_intelligence",
            "name": "Load Board Rate Intelligence",
            "description": "Suggest optimal rates based on market conditions",
            "category": "loadboard"
        },
        {
            "id": "customer_relationship_monitor",
            "name": "Customer Relationship Monitor",
            "description": "Track payment patterns and customer behavior",
            "category": "customer_relationship"
        },
        {
            "id": "equipment_maintenance_predictor",
            "name": "Equipment & Maintenance Predictor",
            "description": "Predict maintenance needs and service intervals",
            "category": "equipment"
        },
        {
            "id": "document_management_assistant",
            "name": "Document Management Assistant",
            "description": "Auto-organize uploads and track document status",
            "category": "documents"
        },
        {
            "id": "performance_analytics",
            "name": "Performance Analytics",
            "description": "Calculate driver performance scores",
            "category": "performance"
        },
        {
            "id": "route_fuel_optimizer",
            "name": "Route & Fuel Optimizer",
            "description": "Suggest optimal routes and fuel stops",
            "category": "route_optimization"
        },
        {
            "id": "compliance_expiration_manager",
            "name": "Compliance Expiration Manager",
            "description": "Track all expirations (licenses, permits, etc.)",
            "category": "compliance"
        },
        {
            "id": "load_optimization_advisor",
            "name": "Load Optimization Advisor",
            "description": "Suggest load combinations and backhaul opportunities",
            "category": "load_optimization"
        },
        {
            "id": "weather_traffic_intelligence",
            "name": "Weather & Traffic Intelligence",
            "description": "Proactive weather and traffic alerts",
            "category": "weather"
        },
        {
            "id": "customer_service_automation",
            "name": "Customer Service Automation",
            "description": "Draft customer communications",
            "category": "customer_service"
        },
        {
            "id": "vendor_management",
            "name": "Vendor Management",
            "description": "Track vendor performance and costs",
            "category": "vendor_management"
        },
        {
            "id": "multi_leg_load_coordinator",
            "name": "Multi-Leg Load Coordinator",
            "description": "Suggest load splitting strategies",
            "category": "multi_leg_coordination"
        },
        {
            "id": "compliance_score_tracker",
            "name": "Compliance Score Tracker",
            "description": "Monitor FMCSA compliance scores",
            "category": "compliance_tracking"
        }
    ]
    
    return {"functions": functions, "total_count": len(functions)}
