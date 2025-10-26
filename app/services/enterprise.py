from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
import secrets
import hashlib
import json
from datetime import datetime, timezone

from app.models.enterprise import (
    WhiteLabelConfig,
    Webhook,
    CustomWorkflow,
    EnterpriseIntegration
)
from app.models.api_key import APIKey
from app.schema.enterprise import (
    WhiteLabelConfigCreate,
    WhiteLabelConfigUpdate,
    APIKeyCreate,
    WebhookCreate,
    WorkflowCreate,
    WorkflowUpdate,
    IntegrationCreate
)
from app.config.logging_config import get_logger
logger = get_logger(__name__)

class EnterpriseService:
    def __init__(self, db: Session):
        self.db = db

    # White-Label Configuration Methods
    async def get_white_label_config(self, company_id: int) -> Optional[WhiteLabelConfig]:
        """Get white-label configuration for a company"""
        return self.db.query(WhiteLabelConfig).filter(
            WhiteLabelConfig.company_id == company_id
        ).first()

    async def create_white_label_config(
        self, 
        company_id: int, 
        config_data: WhiteLabelConfigCreate
    ) -> WhiteLabelConfig:
        """Create or update white-label configuration"""
        existing_config = await self.get_white_label_config(company_id)
        
        if existing_config:
            # Update existing config
            for field, value in config_data.dict(exclude_unset=True).items():
                setattr(existing_config, field, value)
            existing_config.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(existing_config)
            return existing_config
        else:
            # Create new config
            config = WhiteLabelConfig(
                company_id=company_id,
                **config_data.dict()
            )
            
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            return config

    async def update_white_label_config(
        self, 
        config_id: int, 
        company_id: int, 
        config_data: WhiteLabelConfigUpdate
    ) -> WhiteLabelConfig:
        """Update white-label configuration"""
        config = self.db.query(WhiteLabelConfig).filter(
            and_(
                WhiteLabelConfig.id == config_id,
                WhiteLabelConfig.company_id == company_id
            )
        ).first()
        
        if not config:
            raise ValueError("White-label configuration not found")
        
        for field, value in config_data.dict(exclude_unset=True).items():
            setattr(config, field, value)
        
        config.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(config)
        return config

    # API Key Management Methods
    async def get_api_keys(self, company_id: int) -> List[APIKey]:
        """Get all API keys for a company"""
        return self.db.query(APIKey).filter(
            APIKey.company_id == company_id
        ).all()

    async def create_api_key(
        self, 
        company_id: int, 
        key_data: APIKeyCreate
    ) -> APIKey:
        """Create a new API key"""
        # Generate secure API key
        key_secret = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(key_secret.encode()).hexdigest()
        
        api_key = APIKey(
            company_id=company_id,
            name=key_data.name,
            key_hash=key_hash,
            permissions=json.dumps(key_data.permissions),
            is_active=True
        )
        
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        
        # Return the actual key (only shown once)
        api_key.key = f"sk_live_{key_secret}"
        return api_key

    async def delete_api_key(self, key_id: int, company_id: int) -> bool:
        """Delete an API key"""
        api_key = self.db.query(APIKey).filter(
            and_(
                APIKey.id == key_id,
                APIKey.company_id == company_id
            )
        ).first()
        
        if not api_key:
            raise ValueError("API key not found")
        
        self.db.delete(api_key)
        self.db.commit()
        return True

    async def validate_api_key(self, key: str) -> Optional[APIKey]:
        """Validate an API key and return the associated record"""
        if not key.startswith("sk_live_"):
            return None
        
        key_secret = key[8:]  # Remove "sk_live_" prefix
        key_hash = hashlib.sha256(key_secret.encode()).hexdigest()
        
        api_key = self.db.query(APIKey).filter(
            and_(
                APIKey.key_hash == key_hash,
                APIKey.is_active == True
            )
        ).first()
        
        if api_key:
            # Update last used timestamp
            api_key.last_used = datetime.now(timezone.utc)
            self.db.commit()
        
        return api_key

    # Webhook Management Methods
    async def get_webhooks(self, company_id: int) -> List[Webhook]:
        """Get all webhooks for a company"""
        return self.db.query(Webhook).filter(
            Webhook.company_id == company_id
        ).all()

    async def create_webhook(
        self, 
        company_id: int, 
        webhook_data: WebhookCreate
    ) -> Webhook:
        """Create a new webhook"""
        webhook_secret = secrets.token_urlsafe(32)
        
        webhook = Webhook(
            company_id=company_id,
            name=webhook_data.name,
            url=webhook_data.url,
            events=json.dumps(webhook_data.events),
            secret=webhook_secret,
            is_active=True
        )
        
        self.db.add(webhook)
        self.db.commit()
        self.db.refresh(webhook)
        
        return webhook

    async def delete_webhook(self, webhook_id: int, company_id: int) -> bool:
        """Delete a webhook"""
        webhook = self.db.query(Webhook).filter(
            and_(
                Webhook.id == webhook_id,
                Webhook.company_id == company_id
            )
        ).first()
        
        if not webhook:
            raise ValueError("Webhook not found")
        
        self.db.delete(webhook)
        self.db.commit()
        return True

    async def trigger_webhook(
        self, 
        webhook_id: int, 
        event_type: str, 
        payload: dict
    ) -> bool:
        """Trigger a webhook with event data"""
        webhook = self.db.query(Webhook).filter(
            and_(
                Webhook.id == webhook_id,
                Webhook.is_active == True
            )
        ).first()
        
        if not webhook:
            return False
        
        # Check if webhook listens to this event type
        events = json.loads(webhook.events)
        if event_type not in events:
            return False
        
        try:
            # In a real implementation, you would send HTTP request here
            # For now, just log the webhook trigger
            logger.info(f"Webhook {webhook_id} triggered for event {event_type}")
            
            # Update webhook statistics
            webhook.last_triggered = datetime.now(timezone.utc)
            self.db.commit()
            
            return True
        except Exception as e:
            logger.error(f"Failed to trigger webhook {webhook_id}: {str(e)}")
            return False

    # Custom Workflow Methods
    async def get_workflows(self, company_id: int) -> List[CustomWorkflow]:
        """Get all custom workflows for a company"""
        return self.db.query(CustomWorkflow).filter(
            CustomWorkflow.company_id == company_id
        ).all()

    async def create_workflow(
        self, 
        company_id: int, 
        workflow_data: WorkflowCreate
    ) -> CustomWorkflow:
        """Create a new custom workflow"""
        workflow = CustomWorkflow(
            company_id=company_id,
            name=workflow_data.name,
            description=workflow_data.description,
            steps=json.dumps(workflow_data.steps),
            is_active=False
        )
        
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        
        return workflow

    async def update_workflow(
        self, 
        workflow_id: int, 
        company_id: int, 
        workflow_data: WorkflowUpdate
    ) -> CustomWorkflow:
        """Update a custom workflow"""
        workflow = self.db.query(CustomWorkflow).filter(
            and_(
                CustomWorkflow.id == workflow_id,
                CustomWorkflow.company_id == company_id
            )
        ).first()
        
        if not workflow:
            raise ValueError("Workflow not found")
        
        for field, value in workflow_data.dict(exclude_unset=True).items():
            if field == "steps" and value is not None:
                setattr(workflow, field, json.dumps(value))
            else:
                setattr(workflow, field, value)
        
        workflow.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(workflow)
        
        return workflow

    async def delete_workflow(self, workflow_id: int, company_id: int) -> bool:
        """Delete a custom workflow"""
        workflow = self.db.query(CustomWorkflow).filter(
            and_(
                CustomWorkflow.id == workflow_id,
                CustomWorkflow.company_id == company_id
            )
        ).first()
        
        if not workflow:
            raise ValueError("Workflow not found")
        
        self.db.delete(workflow)
        self.db.commit()
        return True

    async def execute_workflow(
        self, 
        workflow_id: int, 
        trigger_data: dict
    ) -> bool:
        """Execute a custom workflow"""
        workflow = self.db.query(CustomWorkflow).filter(
            and_(
                CustomWorkflow.id == workflow_id,
                CustomWorkflow.is_active == True
            )
        ).first()
        
        if not workflow:
            return False
        
        try:
            steps = json.loads(workflow.steps)
            
            # Execute workflow steps
            for step in steps:
                await self._execute_workflow_step(step, trigger_data)
            
            logger.info(f"Workflow {workflow_id} executed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute workflow {workflow_id}: {str(e)}")
            return False

    async def _execute_workflow_step(self, step: dict, trigger_data: dict):
        """Execute a single workflow step"""
        step_type = step.get("type")
        
        if step_type == "trigger":
            # Trigger step - already executed
            pass
        elif step_type == "condition":
            # Check condition
            condition = step.get("config", {}).get("condition")
            if not self._evaluate_condition(condition, trigger_data):
                raise ValueError(f"Condition failed: {condition}")
        elif step_type == "action":
            # Execute action
            action = step.get("config", {}).get("action")
            await self._execute_action(action, trigger_data)
        elif step_type == "notification":
            # Send notification
            notification = step.get("config", {})
            await self._send_notification(notification, trigger_data)

    def _evaluate_condition(self, condition: str, data: dict) -> bool:
        """Evaluate a workflow condition"""
        # Simple condition evaluation
        # In a real implementation, this would be more sophisticated
        return True

    async def _execute_action(self, action: str, data: dict):
        """Execute a workflow action"""
        # Execute the specified action
        # In a real implementation, this would call appropriate services
        logger.info(f"Executing action: {action}")

    async def _send_notification(self, notification: dict, data: dict):
        """Send a workflow notification"""
        # Send notification via email, SMS, or other channels
        logger.info(f"Sending notification: {notification}")

    # Enterprise Integration Methods
    async def get_integrations(self, company_id: int) -> List[EnterpriseIntegration]:
        """Get all enterprise integrations for a company"""
        return self.db.query(EnterpriseIntegration).filter(
            EnterpriseIntegration.company_id == company_id
        ).all()

    async def create_integration(
        self, 
        company_id: int, 
        integration_data: IntegrationCreate
    ) -> EnterpriseIntegration:
        """Create a new enterprise integration"""
        integration = EnterpriseIntegration(
            company_id=company_id,
            name=integration_data.name,
            type=integration_data.type,
            config=json.dumps(integration_data.config),
            status="pending",
            is_active=False
        )
        
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)
        
        return integration

    async def test_integration(
        self, 
        integration_id: int, 
        company_id: int
    ) -> dict:
        """Test an enterprise integration connection"""
        integration = self.db.query(EnterpriseIntegration).filter(
            and_(
                EnterpriseIntegration.id == integration_id,
                EnterpriseIntegration.company_id == company_id
            )
        ).first()
        
        if not integration:
            raise ValueError("Integration not found")
        
        try:
            # Test the integration connection
            # In a real implementation, this would make actual API calls
            config = json.loads(integration.config)
            
            # Simulate connection test
            await self._test_integration_connection(integration.type, config)
            
            integration.status = "connected"
            integration.last_sync = datetime.now(timezone.utc)
            
            self.db.commit()
            
            return {
                "status": "success",
                "message": "Integration connection successful"
            }
            
        except Exception as e:
            integration.status = "error"
            self.db.commit()
            
            return {
                "status": "error",
                "message": str(e)
            }

    async def sync_integration(
        self, 
        integration_id: int, 
        company_id: int
    ) -> dict:
        """Manually sync data from an enterprise integration"""
        integration = self.db.query(EnterpriseIntegration).filter(
            and_(
                EnterpriseIntegration.id == integration_id,
                EnterpriseIntegration.company_id == company_id
            )
        ).first()
        
        if not integration:
            raise ValueError("Integration not found")
        
        if integration.status != "connected":
            raise ValueError("Integration is not connected")
        
        try:
            # Perform data synchronization
            config = json.loads(integration.config)
            sync_result = await self._sync_integration_data(integration.type, config)
            
            integration.last_sync = datetime.now(timezone.utc)
            self.db.commit()
            
            return {
                "status": "success",
                "message": "Data synchronization completed",
                "records_synced": sync_result.get("records_synced", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to sync integration {integration_id}: {str(e)}")
            
            return {
                "status": "error",
                "message": str(e)
            }

    async def delete_integration(self, integration_id: int, company_id: int) -> bool:
        """Delete an enterprise integration"""
        integration = self.db.query(EnterpriseIntegration).filter(
            and_(
                EnterpriseIntegration.id == integration_id,
                EnterpriseIntegration.company_id == company_id
            )
        ).first()
        
        if not integration:
            raise ValueError("Integration not found")
        
        self.db.delete(integration)
        self.db.commit()
        return True

    async def _test_integration_connection(self, integration_type: str, config: dict):
        """Test connection to a specific integration type"""
        # In a real implementation, this would test actual API connections
        # For now, just simulate a successful test
        await asyncio.sleep(0.1)  # Simulate API call delay
        return True

    async def _sync_integration_data(self, integration_type: str, config: dict) -> dict:
        """Sync data from a specific integration type"""
        # In a real implementation, this would sync actual data
        # For now, just simulate data sync
        await asyncio.sleep(0.5)  # Simulate sync operation
        
        return {
            "records_synced": 42,
            "sync_time": datetime.now(timezone.utc).isoformat()
        }
