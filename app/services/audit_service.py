"""
Audit Service for Security and Compliance Logging
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from app.models.audit_log import AuditLog, SecurityEvent, APIAccessLog
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class AuditService:
    """
    Service for managing audit logs and security events
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_authentication_event(
        self,
        action: str,
        user_id: Optional[str] = None,
        company_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log authentication-related events"""
        try:
            audit_entry = AuditLog(
                action=action,
                user_id=user_id,
                company_id=company_id,
                ip_address=ip_address,
                user_agent=user_agent,
                resource_type="authentication",
                status=status,
                error_message=error_message,
                metadata=metadata,
                risk_level=self._get_risk_level_for_auth_action(action, status),
                compliance_category="authentication",
                retention_period="7_years"
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.info(f"Authentication event logged: {action}", extra={
                "extra_fields": {
                    "action": action,
                    "user_id": user_id,
                    "company_id": company_id,
                    "status": status
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to log authentication event: {e}")
            self.db.rollback()
    
    def log_data_access_event(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        company_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log data access events (CRUD operations)"""
        try:
            audit_entry = AuditLog(
                action=action,
                user_id=user_id,
                company_id=company_id,
                ip_address=ip_address,
                user_agent=user_agent,
                resource_type=resource_type,
                resource_id=resource_id,
                changes=changes,
                status=status,
                metadata=metadata,
                risk_level=self._get_risk_level_for_data_action(action, resource_type),
                compliance_category="data_access",
                retention_period="7_years"
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.info(f"Data access event logged: {action} {resource_type}", extra={
                "extra_fields": {
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "user_id": user_id,
                    "company_id": company_id
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to log data access event: {e}")
            self.db.rollback()
    
    def log_financial_event(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        company_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log financial-related events with higher security"""
        try:
            audit_entry = AuditLog(
                action=action,
                user_id=user_id,
                company_id=company_id,
                ip_address=ip_address,
                user_agent=user_agent,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values,
                new_values=new_values,
                status=status,
                metadata=metadata,
                risk_level="high",  # Financial events are always high risk
                compliance_category="financial",
                retention_period="permanent"  # Financial records must be kept permanently
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.info(f"Financial event logged: {action} {resource_type}", extra={
                "extra_fields": {
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "user_id": user_id,
                    "company_id": company_id,
                    "risk_level": "high"
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to log financial event: {e}")
            self.db.rollback()
    
    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        user_id: Optional[str] = None,
        company_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        action_taken: Optional[str] = None
    ):
        """Log security events"""
        try:
            security_event = SecurityEvent(
                event_type=event_type,
                severity=severity,
                description=description,
                user_id=user_id,
                company_id=company_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
                action_taken=action_taken
            )
            
            self.db.add(security_event)
            self.db.commit()
            
            logger.warning(f"Security event logged: {event_type}", extra={
                "extra_fields": {
                    "event_type": event_type,
                    "severity": severity,
                    "user_id": user_id,
                    "company_id": company_id,
                    "action_taken": action_taken
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
            self.db.rollback()
    
    def log_api_access(
        self,
        method: str,
        endpoint: str,
        status_code: str,
        company_id: Optional[str] = None,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_time_ms: Optional[str] = None,
        rate_limit_hit: Optional[str] = None,
        rate_limit_remaining: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None
    ):
        """Log API access for monitoring and abuse detection"""
        try:
            api_log = APIAccessLog(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                company_id=company_id,
                user_id=user_id,
                api_key_id=api_key_id,
                ip_address=ip_address,
                user_agent=user_agent,
                response_time_ms=response_time_ms,
                rate_limit_hit=rate_limit_hit,
                rate_limit_remaining=rate_limit_remaining,
                query_params=query_params
            )
            
            self.db.add(api_log)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log API access: {e}")
            self.db.rollback()
    
    def get_audit_logs(
        self,
        company_id: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """Get audit logs with filtering"""
        try:
            query = self.db.query(AuditLog)
            
            if company_id:
                query = query.filter(AuditLog.company_id == company_id)
            
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            
            if action:
                query = query.filter(AuditLog.action == action)
            
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)
            
            if start_date:
                query = query.filter(AuditLog.timestamp >= start_date)
            
            if end_date:
                query = query.filter(AuditLog.timestamp <= end_date)
            
            return query.order_by(desc(AuditLog.timestamp)).offset(offset).limit(limit).all()
            
        except Exception as e:
            logger.error(f"Failed to get audit logs: {e}")
            return []
    
    def get_security_events(
        self,
        company_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        resolved: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SecurityEvent]:
        """Get security events with filtering"""
        try:
            query = self.db.query(SecurityEvent)
            
            if company_id:
                query = query.filter(SecurityEvent.company_id == company_id)
            
            if event_type:
                query = query.filter(SecurityEvent.event_type == event_type)
            
            if severity:
                query = query.filter(SecurityEvent.severity == severity)
            
            if resolved is not None:
                query = query.filter(SecurityEvent.resolved == resolved)
            
            if start_date:
                query = query.filter(SecurityEvent.timestamp >= start_date)
            
            if end_date:
                query = query.filter(SecurityEvent.timestamp <= end_date)
            
            return query.order_by(desc(SecurityEvent.timestamp)).offset(offset).limit(limit).all()
            
        except Exception as e:
            logger.error(f"Failed to get security events: {e}")
            return []
    
    def _get_risk_level_for_auth_action(self, action: str, status: str) -> str:
        """Determine risk level for authentication actions"""
        if status == "failure":
            if action in ["LOGIN", "PASSWORD_RESET"]:
                return "high"
            elif action in ["LOGOUT"]:
                return "low"
            else:
                return "medium"
        else:
            if action in ["LOGIN", "PASSWORD_RESET"]:
                return "medium"
            else:
                return "low"
    
    def _get_risk_level_for_data_action(self, action: str, resource_type: str) -> str:
        """Determine risk level for data access actions"""
        if action in ["DELETE"]:
            return "high"
        elif action in ["UPDATE"] and resource_type in ["user", "company", "financial"]:
            return "high"
        elif action in ["CREATE"] and resource_type in ["user", "financial"]:
            return "medium"
        else:
            return "low"
    
    def cleanup_old_logs(self, retention_days: int = 365):
        """Clean up old audit logs based on retention policy"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Delete old audit logs (except those marked as permanent)
            deleted_count = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.timestamp < cutoff_date,
                    AuditLog.retention_period != "permanent"
                )
            ).delete()
            
            self.db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old audit logs")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
            self.db.rollback()
            return 0

