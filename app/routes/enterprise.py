from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.config.db import get_db
from app.routes.user import get_current_user
from app.models.userModels import Users
from app.models.userModels import Companies
from app.schema.enterprise import (
    WhiteLabelConfigCreate,
    WhiteLabelConfigUpdate,
    WhiteLabelConfigResponse,
    APIKeyCreate,
    APIKeyResponse,
    WebhookCreate,
    WebhookResponse,
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    IntegrationCreate,
    IntegrationResponse
)
from app.services.enterprise import EnterpriseService

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])

def get_current_company_id(current_user: Users = Depends(get_current_user)) -> int:
    """Get current user's company ID"""
    return current_user.company_id

logger = logging.getLogger(__name__)

@router.get("/subscription-status")
async def get_subscription_status(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id)
):
    """Get current subscription status and tier"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return {
        "tier": current_user.subscription_tier,
        "is_enterprise": current_user.subscription_tier == "enterprise",
        "is_professional": current_user.subscription_tier in ["professional", "enterprise"],
        "features": {
            "white_label": current_user.subscription_tier == "enterprise",
            "advanced_api": current_user.subscription_tier == "enterprise",
            "custom_workflows": current_user.subscription_tier == "enterprise",
            "enterprise_integrations": current_user.subscription_tier == "enterprise",
            "multi_leg_dispatch": current_user.subscription_tier in ["professional", "enterprise"],
            "transloading": current_user.subscription_tier in ["professional", "enterprise"],
            "advanced_ocr": current_user.subscription_tier in ["professional", "enterprise"],
            "container_tracking": current_user.subscription_tier in ["professional", "enterprise"],
            "automated_dispatch": current_user.subscription_tier in ["professional", "enterprise"]
        }
    }

# White-Label Configuration Endpoints
@router.get("/white-label/config", response_model=WhiteLabelConfigResponse)
async def get_white_label_config(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get white-label configuration for the company"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    config = await service.get_white_label_config(company_id)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="White-label configuration not found"
        )
    
    return config

@router.post("/white-label/config", response_model=WhiteLabelConfigResponse)
async def create_white_label_config(
    config_data: WhiteLabelConfigCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create or update white-label configuration"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    config = await service.create_white_label_config(company_id, config_data)
    
    logger.info(f"White-label config created/updated for company {company_id}")
    return config

@router.put("/white-label/config/{config_id}", response_model=WhiteLabelConfigResponse)
async def update_white_label_config(
    config_id: int,
    config_data: WhiteLabelConfigUpdate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Update white-label configuration"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    config = await service.update_white_label_config(config_id, company_id, config_data)
    
    logger.info(f"White-label config {config_id} updated for company {company_id}")
    return config

# API Management Endpoints
@router.get("/api-keys", response_model=List[APIKeyResponse])
async def get_api_keys(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all API keys for the company"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    keys = await service.get_api_keys(company_id)
    return keys

@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new API key"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    api_key = await service.create_api_key(company_id, key_data)
    
    logger.info(f"API key created for company {company_id}")
    return api_key

@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Delete an API key"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    await service.delete_api_key(key_id, company_id)
    
    logger.info(f"API key {key_id} deleted for company {company_id}")
    return {"message": "API key deleted successfully"}

# Webhook Management Endpoints
@router.get("/webhooks", response_model=List[WebhookResponse])
async def get_webhooks(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all webhooks for the company"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    webhooks = await service.get_webhooks(company_id)
    return webhooks

@router.post("/webhooks", response_model=WebhookResponse)
async def create_webhook(
    webhook_data: WebhookCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new webhook"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    webhook = await service.create_webhook(company_id, webhook_data)
    
    logger.info(f"Webhook created for company {company_id}")
    return webhook

@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Delete a webhook"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    await service.delete_webhook(webhook_id, company_id)
    
    logger.info(f"Webhook {webhook_id} deleted for company {company_id}")
    return {"message": "Webhook deleted successfully"}

# Custom Workflow Endpoints
@router.get("/workflows", response_model=List[WorkflowResponse])
async def get_workflows(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all custom workflows for the company"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    workflows = await service.get_workflows(company_id)
    return workflows

@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(
    workflow_data: WorkflowCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new custom workflow"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    workflow = await service.create_workflow(company_id, workflow_data)
    
    logger.info(f"Workflow created for company {company_id}")
    return workflow

@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    workflow_data: WorkflowUpdate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Update a custom workflow"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    workflow = await service.update_workflow(workflow_id, company_id, workflow_data)
    
    logger.info(f"Workflow {workflow_id} updated for company {company_id}")
    return workflow

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Delete a custom workflow"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    await service.delete_workflow(workflow_id, company_id)
    
    logger.info(f"Workflow {workflow_id} deleted for company {company_id}")
    return {"message": "Workflow deleted successfully"}

# Enterprise Integration Endpoints
@router.get("/integrations", response_model=List[IntegrationResponse])
async def get_integrations(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all enterprise integrations for the company"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    integrations = await service.get_integrations(company_id)
    return integrations

@router.post("/integrations", response_model=IntegrationResponse)
async def create_integration(
    integration_data: IntegrationCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new enterprise integration"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    integration = await service.create_integration(company_id, integration_data)
    
    logger.info(f"Integration created for company {company_id}")
    return integration

@router.post("/integrations/{integration_id}/test")
async def test_integration(
    integration_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Test an enterprise integration connection"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    result = await service.test_integration(integration_id, company_id)
    
    logger.info(f"Integration {integration_id} tested for company {company_id}")
    return result

@router.post("/integrations/{integration_id}/sync")
async def sync_integration(
    integration_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Manually sync data from an enterprise integration"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    result = await service.sync_integration(integration_id, company_id)
    
    logger.info(f"Integration {integration_id} synced for company {company_id}")
    return result

@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Delete an enterprise integration"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    await service.delete_integration(integration_id, company_id)
    
    logger.info(f"Integration {integration_id} deleted for company {company_id}")
    return {"message": "Integration deleted successfully"}

@router.get("/integrations")
async def get_integrations(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all enterprise integrations for a company"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    integrations = await service.get_integrations(company_id)
    return integrations

@router.get("/api-keys")
async def get_api_keys(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all API keys for a company"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    api_keys = await service.get_api_keys(company_id)
    return api_keys

@router.get("/webhooks")
async def get_webhooks(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all webhooks for a company"""
    if current_user.subscription_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise subscription required"
        )
    
    service = EnterpriseService(db)
    webhooks = await service.get_webhooks(company_id)
    return webhooks
