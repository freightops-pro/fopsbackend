from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import uuid
from threading import Lock

from app.models.port import Port, PortCredential, PortAuditLog, CompanyPortAddon
from app.services.credential_encryption_service import CredentialEncryptionService
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class PortCredentialService:
    """
    Port credential management with encryption and rotation
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.encryption_service = CredentialEncryptionService()
        self.lock = Lock()
    
    def create_credential(
        self,
        port_id: str,
        company_id: str,
        credentials: Dict[str, Any],
        credential_type: str,
        user_id: str,
        expires_at: Optional[datetime] = None
    ) -> PortCredential:
        """Create new port credential with encryption"""
        with self.lock:
            try:
                # Validate port exists
                port = self.db.query(Port).filter(Port.id == port_id).first()
                if not port:
                    raise ValueError("Port not found")
                
                # Validate credential structure
                self._validate_credentials(credentials, port.auth_type.value)
                
                # Encrypt credentials
                encrypted = self.encryption_service.encrypt_credentials(credentials)
                
                # Create credential
                credential = PortCredential(
                    id=str(uuid.uuid4()),
                    port_id=port_id,
                    company_id=company_id,
                    encrypted_credentials=encrypted,
                    credential_type=credential_type,
                    expires_at=expires_at or (datetime.utcnow() + timedelta(days=90)),
                    created_by=user_id,
                    validation_status="pending"
                )
                
                self.db.add(credential)
                
                # Audit log
                self._create_audit_log(
                    port_id=port_id,
                    company_id=company_id,
                    user_id=user_id,
                    credential_id=credential.id,
                    action_type="credential_created",
                    action_status="success"
                )
                
                self.db.commit()
                self.db.refresh(credential)
                
                logger.info(f"Port credential created for {port.port_code}", extra={
                    "extra_fields": {
                        "company_id": company_id,
                        "port_code": port.port_code
                    }
                })
                
                return credential
                
            except Exception as e:
                self.db.rollback()
                logger.error("Failed to create credential", exc_info=True)
                raise
    
    def get_decrypted_credential(
        self,
        credential_id: str,
        company_id: str
    ) -> Dict[str, Any]:
        """Retrieve and decrypt credential with company isolation"""
        credential = self.db.query(PortCredential).filter(
            PortCredential.id == credential_id,
            PortCredential.company_id == company_id,
            PortCredential.is_active == True
        ).first()
        
        if not credential:
            raise ValueError("Credential not found or access denied")
        
        if credential.expires_at and credential.expires_at < datetime.utcnow():
            raise ValueError("Credential has expired")
        
        # Decrypt
        decrypted = self.encryption_service.decrypt_credentials(
            credential.encrypted_credentials
        )
        
        # Audit log
        self._create_audit_log(
            port_id=credential.port_id,
            company_id=company_id,
            credential_id=credential_id,
            action_type="credential_accessed",
            action_status="success"
        )
        
        return decrypted
    
    def get_company_credentials(
        self,
        company_id: str,
        port_code: Optional[str] = None
    ) -> List[PortCredential]:
        """Get all credentials for a company, optionally filtered by port"""
        query = self.db.query(PortCredential).filter(
            PortCredential.company_id == company_id,
            PortCredential.is_active == True
        )
        
        if port_code:
            query = query.join(Port).filter(Port.port_code == port_code)
        
        return query.all()
    
    def rotate_credential(
        self,
        credential_id: str,
        company_id: str,
        new_credentials: Dict[str, Any],
        user_id: str
    ) -> PortCredential:
        """
        Zero-downtime credential rotation
        
        Process:
        1. Create new credential
        2. Mark old for deactivation (24h grace period)
        3. Validate new credential works
        """
        old_credential = self.db.query(PortCredential).filter(
            PortCredential.id == credential_id,
            PortCredential.company_id == company_id
        ).first()
        
        if not old_credential:
            raise ValueError("Credential not found")
        
        try:
            # Create new credential
            new_credential = self.create_credential(
                port_id=old_credential.port_id,
                company_id=company_id,
                credentials=new_credentials,
                credential_type=old_credential.credential_type,
                user_id=user_id
            )
            
            # Schedule old credential deactivation
            old_credential.rotation_required = True
            old_credential.rotation_scheduled_at = datetime.utcnow() + timedelta(hours=24)
            
            self._create_audit_log(
                port_id=old_credential.port_id,
                company_id=company_id,
                user_id=user_id,
                credential_id=credential_id,
                action_type="credential_rotated",
                action_status="success"
            )
            
            self.db.commit()
            
            return new_credential
            
        except Exception as e:
            self.db.rollback()
            logger.error("Credential rotation failed", exc_info=True)
            raise
    
    def validate_credential(self, credential_id: str) -> bool:
        """Validate credential by testing with port API"""
        credential = self.db.query(PortCredential).filter(
            PortCredential.id == credential_id
        ).first()
        
        if not credential:
            return False
        
        try:
            # TODO: Implement actual port API validation
            # For now, just mark as valid if it can be decrypted
            self.encryption_service.decrypt_credentials(credential.encrypted_credentials)
            
            credential.validation_status = "valid"
            credential.last_validated = datetime.utcnow()
            credential.consecutive_failures = 0
            credential.last_error = None
            credential.last_success_at = datetime.utcnow()
            
            self.db.commit()
            return True
            
        except Exception as e:
            credential.validation_status = "invalid"
            credential.consecutive_failures += 1
            credential.last_error = str(e)
            credential.last_failure_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.warning("Credential validation failed", extra={
                "extra_fields": {
                    "credential_id": credential_id,
                    "failures": credential.consecutive_failures
                }
            })
            
            return False
    
    def deactivate_credential(self, credential_id: str, company_id: str, user_id: str) -> bool:
        """Deactivate a credential"""
        credential = self.db.query(PortCredential).filter(
            PortCredential.id == credential_id,
            PortCredential.company_id == company_id
        ).first()
        
        if not credential:
            return False
        
        credential.is_active = False
        
        # Audit log
        self._create_audit_log(
            port_id=credential.port_id,
            company_id=company_id,
            user_id=user_id,
            credential_id=credential_id,
            action_type="credential_deactivated",
            action_status="success"
        )
        
        self.db.commit()
        return True
    
    def _validate_credentials(self, credentials: Dict[str, Any], auth_type: str):
        """Validate credential structure based on auth type"""
        required_fields = {
            "api_key": ["api_key"],
            "oauth2": ["client_id", "client_secret", "token_url"],
            "jwt": ["private_key", "issuer", "audience"],
            "client_cert": ["certificate_path", "private_key_path"],
            "basic_auth": ["username", "password"]
        }
        
        required = required_fields.get(auth_type, [])
        for field in required:
            if field not in credentials:
                raise ValueError(f"Missing required field: {field}")
    
    def _create_audit_log(
        self,
        port_id: str,
        company_id: str,
        action_type: str,
        action_status: str,
        **kwargs
    ):
        """Create audit log entry"""
        log = PortAuditLog(
            id=str(uuid.uuid4()),
            port_id=port_id,
            company_id=company_id,
            action_type=action_type,
            action_status=action_status,
            **kwargs
        )
        self.db.add(log)









