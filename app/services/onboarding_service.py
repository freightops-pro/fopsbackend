from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.onboarding import OnboardingFlow, OnboardingTask

# Default checklist template - can be customized
DEFAULT_TASKS = [
    "Collect Personal Info",
    "Employment Agreement",
    "W-4 & I-9 Forms",
    "Safety Training",
    "DOT Physical (if applicable)",
    "Drug & Alcohol Test",
    "Equipment Assignment",
    "Final Review"
]

# In-memory template storage (in production, use database)
current_template = DEFAULT_TASKS.copy()

def get_template() -> List[str]:
    return current_template.copy()

def update_template(tasks: List[str]) -> List[str]:
    global current_template
    current_template = [task.strip() for task in tasks if task.strip()]
    return current_template.copy()

def ensure_onboarding_schema(db: Session):
    """Ensure onboarding_flows.employee_id is VARCHAR to match Employee.id (string)."""
    try:
        # Works for Postgres; harmless if already correct
        db.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name='onboarding_flows' AND column_name='employee_id' AND data_type NOT IN ('character varying','text')
                ) THEN
                    ALTER TABLE onboarding_flows ALTER COLUMN employee_id TYPE VARCHAR USING employee_id::text;
                END IF;
            END$$;
        """)
        db.commit()
    except Exception:
        db.rollback()
        # Best effort; ignore if database doesn't support DO $$ (e.g., SQLite)
        try:
            db.execute("ALTER TABLE onboarding_flows ALTER COLUMN employee_id TYPE VARCHAR")
            db.commit()
        except Exception:
            db.rollback()

def create_onboarding_flow(db: Session, employee_id: str, employee_name: str, position: Optional[str]) -> OnboardingFlow:
    ensure_onboarding_schema(db)
    flow = OnboardingFlow(employee_id=employee_id, employee_name=employee_name, position=position)
    db.add(flow)
    db.flush()  # get flow.id
    tasks = []
    for idx, name in enumerate(current_template, start=1):
        task = OnboardingTask(flow_id=flow.id, name=name, order=idx)
        db.add(task)
        tasks.append(task)
    db.commit()
    db.refresh(flow)
    return flow

def list_flows(db: Session) -> List[OnboardingFlow]:
    ensure_onboarding_schema(db)
    return db.query(OnboardingFlow).order_by(OnboardingFlow.started_at.desc()).all()

def get_flow(db: Session, flow_id: int) -> Optional[OnboardingFlow]:
    return db.query(OnboardingFlow).filter(OnboardingFlow.id == flow_id).first()

def update_task_completion(db: Session, task_id: int, completed: bool) -> Optional[OnboardingTask]:
    task = db.query(OnboardingTask).filter(OnboardingTask.id == task_id).first()
    if not task:
        return None
    task.completed = completed
    task.completed_at = datetime.utcnow() if completed else None
    db.add(task)
    # If all tasks complete, mark flow complete
    flow = task.flow
    if flow:
        if all(t.completed for t in flow.tasks):
            flow.status = "Complete"
            flow.completed_at = datetime.utcnow()
        else:
            flow.status = "In Progress"
            flow.completed_at = None
        db.add(flow)
    db.commit()
    db.refresh(task)
    return task

def get_onboarding_stats(db: Session) -> dict:
    """Calculate live onboarding statistics"""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Get all flows
    all_flows = db.query(OnboardingFlow).all()
    
    # Active flows
    active_count = len([f for f in all_flows if f.status == "In Progress"])
    
    # Completed this month
    completed_this_month = len([
        f for f in all_flows 
        if f.completed_at and f.completed_at >= month_start
    ])
    
    # Average completion time (for completed flows)
    completed_flows = [f for f in all_flows if f.completed_at and f.started_at]
    if completed_flows:
        total_days = sum([
            (f.completed_at - f.started_at).days 
            for f in completed_flows
        ])
        avg_days = round(total_days / len(completed_flows))
    else:
        avg_days = 0
    
    # Overdue tasks (flows started > 14 days ago and not complete)
    two_weeks_ago = now - timedelta(days=14)
    overdue_count = len([
        f for f in all_flows 
        if f.status == "In Progress" and f.started_at < two_weeks_ago
    ])
    
    return {
        "active": active_count,
        "completed_this_month": completed_this_month,
        "avg_completion_days": avg_days,
        "overdue": overdue_count
    }
