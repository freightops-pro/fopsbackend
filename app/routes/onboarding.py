from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.config.db import get_db
from app.schema.onboardingSchema import OnboardingFlowOut, OnboardingFlowCreate, OnboardingTaskUpdate, OnboardingTaskOut
from app.services.onboarding_service import (
    create_onboarding_flow, list_flows, get_flow, update_task_completion,
    get_template, update_template, get_onboarding_stats
)

router = APIRouter(prefix="/api/hr/onboarding", tags=["Onboarding"])

@router.get("/flows", response_model=List[OnboardingFlowOut])
def list_onboarding_flows(db: Session = Depends(get_db)):
    return list_flows(db)

@router.post("/flows", response_model=OnboardingFlowOut, status_code=201)
def start_onboarding(flow_in: OnboardingFlowCreate, db: Session = Depends(get_db)):
    flow = create_onboarding_flow(db, flow_in.employee_id, flow_in.employee_name, flow_in.position)
    return flow

@router.get("/flows/{flow_id}", response_model=OnboardingFlowOut)
def get_onboarding_flow(flow_id: int, db: Session = Depends(get_db)):
    flow = get_flow(db, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Onboarding flow not found")
    return flow

@router.patch("/tasks/{task_id}", response_model=OnboardingTaskOut)
def update_onboarding_task(task_id: int, task_update: OnboardingTaskUpdate, db: Session = Depends(get_db)):
    task = update_task_completion(db, task_id, task_update.completed)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/template")
def get_onboarding_template():
    return {"tasks": get_template()}

@router.put("/template")
def update_onboarding_template(template: dict):
    tasks = template.get("tasks", [])
    if not tasks or not isinstance(tasks, list):
        raise HTTPException(status_code=400, detail="Invalid template format")
    updated = update_template(tasks)
    return {"tasks": updated}

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    return get_onboarding_stats(db)
