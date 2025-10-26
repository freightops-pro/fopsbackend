"""
Alex AI API Routes - Executive Assistant for Managers and Directors
Access: Manager, Director, Executive roles only
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.config.db import get_db
from app.models.ai_insights import AIInsight
from app.models.userModels import Users, Companies
from app.models.chat import Conversation, Message
from app.services.alex_ai import alex_ai
from app.routes.user import get_current_user
import uuid

router = APIRouter(prefix="/api/alex", tags=["Alex AI"])

def check_executive_access(user: Users):
    """Check if user has executive access (Manager, Director, Executive, Admin)"""
    executive_roles = ["manager", "director", "executive", "admin"]
    if user.role.lower() not in executive_roles:
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Alex AI is only available for Manager, Director, Executive, and Admin roles."
        )

@router.get("/insights")
async def get_alex_insights(
    function_category: Optional[str] = Query(None, description="Filter by function category"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    status: Optional[str] = Query("pending", description="Filter by status"),
    limit: int = Query(50, description="Number of insights to return"),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Alex's executive insights for the user's subscriber"""
    check_executive_access(current_user)
    
    try:
        # Get user's company and subscriber
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        query = db.query(AIInsight).filter(
            AIInsight.subscriber_id == company.subscriber_id,
            AIInsight.ai_source == "alex"
        )
        
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
        raise HTTPException(status_code=500, detail=f"Error fetching Alex insights: {str(e)}")

@router.post("/insights/{insight_id}/dismiss")
async def dismiss_alex_insight(
    insight_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dismiss an Alex insight"""
    check_executive_access(current_user)
    
    try:
        # Get user's company and subscriber
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        insight = db.query(AIInsight).filter(
            AIInsight.id == insight_id,
            AIInsight.subscriber_id == company.subscriber_id,
            AIInsight.ai_source == "alex"
        ).first()
        
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        insight.status = "dismissed"
        insight.dismissed_by = current_user.id
        db.commit()
        
        return {"message": "Alex insight dismissed successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error dismissing Alex insight: {str(e)}")

@router.post("/chat")
async def chat_with_alex(
    message: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat with Alex AI executive assistant"""
    check_executive_access(current_user)
    
    try:
        # Get user's company and subscriber
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        # Create or find AI conversation
        ai_conversation = db.query(Conversation).filter(
            Conversation.subscriber_id == company.subscriber_id,
            Conversation.ai_source == "alex",
            Conversation.is_ai_conversation == True,
            Conversation.participant1_id == current_user.id
        ).first()
        
        if not ai_conversation:
            ai_conversation = Conversation(
                id=str(uuid.uuid4()),
                subscriber_id=company.subscriber_id,
                company_id=company.id,
                conversation_type="ai_conversation",
                ai_source="alex",
                is_ai_conversation=True,
                participant1_id=current_user.id,
                participant1_type="user",
                participant2_id="alex",
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
        
        # Generate Alex's response (mock for now - would integrate with LLM)
        alex_response = f"Executive Analysis: Based on your query '{message}', here's my strategic assessment with data-driven insights and actionable recommendations..."
        
        # Save Alex's response
        alex_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=ai_conversation.id,
            sender_id="alex",
            sender_type="ai",
            company_id=company.id,
            content=alex_response
        )
        db.add(alex_message)
        
        db.commit()
        
        return {
            "conversation_id": ai_conversation.id,
            "user_message": user_message,
            "alex_response": alex_message
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error chatting with Alex: {str(e)}")

@router.get("/kpis")
async def get_executive_kpis(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get real-time KPIs for executive dashboard"""
    check_executive_access(current_user)
    
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        # Get all companies for subscriber
        companies = db.query(Companies).filter(Companies.subscriber_id == company.subscriber_id).all()
        
        # Calculate KPIs
        total_revenue = 0
        total_expenses = 0
        active_loads = 0
        total_drivers = 0
        
        for comp in companies:
            # Revenue (mock calculation)
            total_revenue += comp.walletBalance or 0
            
            # Active loads
            from app.models.simple_load import SimpleLoad
            company_loads = db.query(SimpleLoad).filter(
                SimpleLoad.company_id == comp.id,
                SimpleLoad.status.in_(["assigned", "in_transit"])
            ).count()
            active_loads += company_loads
            
            # Total drivers
            company_drivers = db.query(Driver).filter(Driver.companyId == comp.id).count()
            total_drivers += company_drivers
        
        kpis = {
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "net_profit": total_revenue - total_expenses,
            "profit_margin": ((total_revenue - total_expenses) / total_revenue * 100) if total_revenue > 0 else 0,
            "active_loads": active_loads,
            "total_drivers": total_drivers,
            "companies_count": len(companies),
            "revenue_per_driver": total_revenue / total_drivers if total_drivers > 0 else 0,
            "utilization_rate": (active_loads / total_drivers * 100) if total_drivers > 0 else 0
        }
        
        return {"kpis": kpis}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching KPIs: {str(e)}")

@router.get("/team-performance")
async def get_team_performance(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get team performance analytics"""
    check_executive_access(current_user)
    
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        # Get all companies for subscriber
        companies = db.query(Companies).filter(Companies.subscriber_id == company.subscriber_id).all()
        
        performance_data = []
        for comp in companies:
            drivers = db.query(Driver).filter(Driver.companyId == comp.id).all()
            
            company_performance = {
                "company_id": comp.id,
                "company_name": comp.name,
                "driver_count": len(drivers),
                "active_drivers": len([d for d in drivers if d.status == "active"]),
                "average_performance": 85 + (hash(comp.id) % 15),  # Mock score
                "top_performers": [],
                "underperformers": []
            }
            
            # Mock performance calculation
            for driver in drivers:
                performance_score = 85 + (hash(driver.id) % 15)
                
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
        
        return {"team_performance": performance_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching team performance: {str(e)}")

@router.get("/strategic-insights")
async def get_strategic_insights(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get strategic recommendations and insights"""
    check_executive_access(current_user)
    
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        # Get recent strategic insights from Alex
        insights = db.query(AIInsight).filter(
            AIInsight.subscriber_id == company.subscriber_id,
            AIInsight.ai_source == "alex",
            AIInsight.function_category.in_(["strategic_planning", "decision_support", "financial_intelligence"])
        ).order_by(AIInsight.created_at.desc()).limit(10).all()
        
        return {"strategic_insights": insights}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching strategic insights: {str(e)}")

# Function-specific endpoints for Alex's 6 functions

@router.post("/executive-dashboard/analyze")
async def analyze_executive_dashboard(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Alex's executive dashboard analysis"""
    check_executive_access(current_user)
    
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await alex_ai.executive_dashboard_intelligence(company.subscriber_id)
        return {"message": "Executive dashboard analysis triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering executive dashboard analysis: {str(e)}")

@router.post("/team-performance/analyze")
async def analyze_team_performance(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Alex's team performance analysis"""
    check_executive_access(current_user)
    
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await alex_ai.team_performance_analytics(company.subscriber_id)
        return {"message": "Team performance analysis triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering team performance analysis: {str(e)}")

@router.post("/financial/analyze")
async def analyze_financial_intelligence(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Alex's financial intelligence analysis"""
    check_executive_access(current_user)
    
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await alex_ai.financial_intelligence(company.subscriber_id)
        return {"message": "Financial intelligence analysis triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering financial intelligence analysis: {str(e)}")

@router.post("/strategic-planning/analyze")
async def analyze_strategic_planning(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Alex's strategic planning analysis"""
    check_executive_access(current_user)
    
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await alex_ai.strategic_planning_assistant(company.subscriber_id)
        return {"message": "Strategic planning analysis triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering strategic planning analysis: {str(e)}")

@router.post("/run-all-functions")
async def run_all_alex_functions(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger all 6 Alex functions for the user's subscriber"""
    check_executive_access(current_user)
    
    try:
        company = db.query(Companies).filter(Companies.id == current_user.companyid).first()
        if not company or not company.subscriber_id:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        await alex_ai.run_all_functions(company.subscriber_id)
        return {"message": "All Alex functions triggered successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering Alex functions: {str(e)}")

@router.get("/functions")
async def get_alex_functions():
    """Get list of Alex's 6 functions"""
    functions = [
        {
            "id": "executive_dashboard_intelligence",
            "name": "Executive Dashboard Intelligence",
            "description": "Real-time KPI monitoring and executive reporting",
            "category": "executive_dashboard"
        },
        {
            "id": "team_performance_analytics",
            "name": "Team Performance Analytics",
            "description": "Team productivity metrics and performance tracking",
            "category": "team_performance"
        },
        {
            "id": "financial_intelligence",
            "name": "Financial Intelligence",
            "description": "P&L analysis, forecasting, and financial insights",
            "category": "financial_intelligence"
        },
        {
            "id": "strategic_planning_assistant",
            "name": "Strategic Planning Assistant",
            "description": "Market opportunity identification and growth recommendations",
            "category": "strategic_planning"
        },
        {
            "id": "meeting_communication_support",
            "name": "Meeting & Communication Support",
            "description": "Generate meeting agendas and executive communications",
            "category": "meeting_support"
        },
        {
            "id": "decision_support",
            "name": "Decision Support",
            "description": "Data-driven recommendations and risk analysis",
            "category": "decision_support"
        }
    ]
    
    return {"functions": functions, "total_count": len(functions)}
