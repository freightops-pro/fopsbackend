"""
Enterprise-specific Pydantic schemas
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class EnterpriseFeature(str, Enum):
    WHITE_LABEL = "white_label"
    CUSTOM_WORKFLOWS = "custom_workflows"
    ADVANCED_API = "advanced_api"
    ENTERPRISE_INTEGRATIONS = "enterprise_integrations"
    MULTI_LOCATION = "multi_location"
    MULTI_AUTHORITY = "multi_authority"
    CUSTOM_REPORTING = "custom_reporting"
    PRIORITY_SUPPORT = "priority_support"

class WhiteLabelConfig(BaseModel):
    custom_domain: Optional[str] = None
    custom_logo_url: Optional[str] = None
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None
    company_name: Optional[str] = None
    support_email: Optional[str] = None

class CustomWorkflowStep(BaseModel):
    id: str
    name: str
    type: str  # 'trigger', 'action', 'condition'
    config: Dict[str, Any]
    order: int

class CustomWorkflow(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Dict[str, Any]
    steps: List[CustomWorkflowStep]
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class APIToken(BaseModel):
    id: Optional[str] = None
    name: str
    token: Optional[str] = None
    permissions: List[str] = []
    usage_count: int = 0
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True

class WebhookEndpoint(BaseModel):
    id: Optional[str] = None
    name: str
    url: str
    events: List[str] = []
    secret: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

class EnterpriseIntegration(BaseModel):
    id: Optional[str] = None
    name: str
    type: str  # 'erp', 'tms', 'eld', 'load_board', 'factoring'
    config: Dict[str, Any]
    is_active: bool = True
    last_sync: Optional[datetime] = None

class EnterpriseSettings(BaseModel):
    company_id: str
    enabled_features: List[EnterpriseFeature] = []
    white_label_config: Optional[WhiteLabelConfig] = None
    custom_workflows: List[CustomWorkflow] = []
    api_tokens: List[APIToken] = []
    webhook_endpoints: List[WebhookEndpoint] = []
    integrations: List[EnterpriseIntegration] = []
    max_api_calls_per_month: int = 100000
    max_webhooks_per_month: int = 10000

class EnterpriseFeatureRequest(BaseModel):
    feature: EnterpriseFeature
    company_id: str
    requested_by: str
    justification: Optional[str] = None
    status: str = "pending"  # 'pending', 'approved', 'rejected'
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

class EnterpriseUsageMetrics(BaseModel):
    company_id: str
    month: str  # YYYY-MM format
    api_calls: int = 0
    webhook_calls: int = 0
    workflow_executions: int = 0
    integration_syncs: int = 0
    custom_reports_generated: int = 0

# Additional schemas for API compatibility
class WhiteLabelConfigCreate(BaseModel):
    custom_domain: Optional[str] = None
    custom_logo_url: Optional[str] = None
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None
    company_name: Optional[str] = None
    support_email: Optional[str] = None

class WhiteLabelConfigUpdate(BaseModel):
    custom_domain: Optional[str] = None
    custom_logo_url: Optional[str] = None
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None
    company_name: Optional[str] = None
    support_email: Optional[str] = None

class WhiteLabelConfigResponse(WhiteLabelConfig):
    id: str
    created_at: datetime
    updated_at: datetime

class APIKeyCreate(BaseModel):
    name: str
    permissions: List[str] = []
    expires_at: Optional[datetime] = None

class APIKeyResponse(APIToken):
    pass

class WebhookCreate(BaseModel):
    name: str
    url: str
    events: List[str] = []
    secret: Optional[str] = None

class WebhookResponse(WebhookEndpoint):
    pass

class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Dict[str, Any]
    steps: List[CustomWorkflowStep]

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    steps: Optional[List[CustomWorkflowStep]] = None
    is_active: Optional[bool] = None

class WorkflowResponse(CustomWorkflow):
    pass

class IntegrationCreate(BaseModel):
    name: str
    type: str  # 'erp', 'tms', 'eld', 'load_board', 'factoring'
    config: Dict[str, Any]

class IntegrationResponse(EnterpriseIntegration):
    pass
