from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.core.password_policy import validate_password
from app.models.company import Company
from app.models.driver import Driver
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.auth import AuthSessionResponse, SessionCompany, SessionUser, UserCreate, UserLogin

logger = logging.getLogger(__name__)

# Token expiry settings
DEFAULT_TOKEN_EXPIRY_MINUTES = 60 * 12  # 12 hours
REMEMBER_ME_TOKEN_EXPIRY_MINUTES = 60 * 24 * 30  # 30 days

# Account lockout settings
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, payload: UserCreate) -> Tuple[User, str]:
        # Validate password strength
        is_valid, errors = validate_password(payload.password, payload.email)
        if not is_valid:
            raise ValueError(f"Password does not meet requirements: {'; '.join(errors)}")

        existing_user = await self.db.execute(select(User).where(User.email == payload.email.lower()))
        if existing_user.scalar_one_or_none():
            raise ValueError("User with this email already exists")

        dot_number = self._normalize_identifier(payload.dot_number)
        mc_number = self._normalize_identifier(payload.mc_number)
        if not dot_number and not mc_number:
            raise ValueError("Provide at least a USDOT or MC number")

        if dot_number:
            existing_dot = await self.db.execute(select(Company).where(Company.dotNumber == dot_number))
            if existing_dot.scalar_one_or_none():
                raise ValueError("A company with this USDOT number already exists")
        if mc_number:
            existing_mc = await self.db.execute(select(Company).where(Company.mcNumber == mc_number))
            if existing_mc.scalar_one_or_none():
                raise ValueError("A company with this MC number already exists")

        company = Company(
            id=str(uuid.uuid4()),
            name=payload.company_name.strip(),
            email=payload.email.lower(),
            phone=payload.contact_phone.strip(),
            subscriptionPlan="pro",
            businessType=payload.business_type,
            dotNumber=dot_number,
            mcNumber=mc_number,
            primaryContactName=f"{payload.first_name.strip()} {payload.last_name.strip()}".strip(),
        )
        self.db.add(company)

        # Generate email verification token
        verification_token = secrets.token_urlsafe(32)

        user = User(
            id=str(uuid.uuid4()),
            email=payload.email.lower(),
            hashed_password=hash_password(payload.password),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            company_id=company.id,
            role=None,
            email_verified=False,
            email_verification_token=verification_token,
            email_verification_sent_at=datetime.utcnow(),
            password_changed_at=datetime.utcnow(),
        )
        self.db.add(user)
        await self.db.flush()

        # Assign TENANT_ADMIN role to new users
        await self._assign_default_role(user.id, "TENANT_ADMIN")

        # Log registration event
        await self._log_audit_event(
            event_type="account.created",
            action=f"User registered: {user.email}",
            user_id=user.id,
            user_email=user.email,
            company_id=company.id,
        )

        await self.db.commit()
        await self.db.refresh(user)

        # Send verification email
        await self._send_verification_email(user)

        token = create_access_token({"sub": user.id})
        return user, token

    async def authenticate(
        self,
        payload: UserLogin,
        ip_address: Optional[str] = None,
        remember_me: bool = False,
    ) -> Tuple[User, str]:
        """Authenticate user with account lockout and remember me support."""
        email_lower = payload.email.lower()

        # Check if account is locked
        result = await self.db.execute(select(User).where(User.email == email_lower))
        user = result.scalar_one_or_none()

        if user and user.locked_until and user.locked_until > datetime.utcnow():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
            await self._log_audit_event(
                event_type="auth.login_failure",
                action=f"Login attempt on locked account: {email_lower}",
                user_id=user.id if user else None,
                user_email=email_lower,
                status="blocked",
                extra_data={"reason": "account_locked", "remaining_minutes": remaining},
            )
            raise ValueError(f"Account is locked. Try again in {remaining} minutes.")

        # Verify credentials
        if not user or not verify_password(payload.password, user.hashed_password):
            if user:
                # Increment failed attempts
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

                # Lock account if max attempts reached
                if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                    await self._log_audit_event(
                        event_type="account.locked",
                        action=f"Account locked after {MAX_FAILED_ATTEMPTS} failed attempts",
                        user_id=user.id,
                        user_email=user.email,
                        company_id=user.company_id,
                    )

                await self.db.commit()

            await self._log_audit_event(
                event_type="auth.login_failure",
                action=f"Failed login attempt: {email_lower}",
                user_id=user.id if user else None,
                user_email=email_lower,
                status="failure",
                extra_data={"ip_address": ip_address},
            )
            raise ValueError("Invalid credentials")

        if not user.is_active:
            await self._log_audit_event(
                event_type="auth.login_failure",
                action=f"Login attempt on disabled account: {email_lower}",
                user_id=user.id,
                user_email=user.email,
                status="blocked",
            )
            raise ValueError("User disabled")

        # Verify company credentials
        company = await self.db.get(Company, user.company_id)
        if not company:
            raise ValueError("Company not found for user")

        verification_code = self._normalize_identifier(payload.verification_code)
        if not verification_code:
            raise ValueError("USDOT or MC number is required for verification")
        if not self._matches_company_identifier(verification_code, company):
            raise ValueError("Unable to verify USDOT/MC credentials for this account")

        # Successful login - reset failed attempts and update last login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = ip_address

        await self._log_audit_event(
            event_type="auth.login_success",
            action=f"Successful login: {email_lower}",
            user_id=user.id,
            user_email=user.email,
            company_id=user.company_id,
            extra_data={"ip_address": ip_address, "remember_me": remember_me},
        )

        await self.db.commit()

        # Create token with extended expiry if "remember me"
        token_expiry = REMEMBER_ME_TOKEN_EXPIRY_MINUTES if remember_me else DEFAULT_TOKEN_EXPIRY_MINUTES
        access_token = create_access_token({"sub": user.id}, expires_delta=timedelta(minutes=token_expiry))

        return user, access_token

    async def build_session(self, user: User, token: str | None = None) -> AuthSessionResponse:
        company = await self.db.get(Company, user.company_id)
        if not company:
            raise ValueError("Company not found for user")

        # Try to get roles from RBAC tables, fall back to legacy role if tables don't exist
        try:
            roles = await self._get_user_roles(user.id)
        except Exception:
            # RBAC tables may not exist yet, use empty list to trigger fallback
            roles = []

        if not roles and user.role:
            roles = [user.role.upper()]
        if not roles:
            roles = ["TENANT_ADMIN"]

        # Check if user is linked to a driver profile
        driver_id = await self._get_driver_id_for_user(user.id)

        session_user = SessionUser(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            roles=roles,
            must_change_password=user.must_change_password,
            email_verified=user.email_verified,
            driver_id=driver_id,
        )

        session_company = SessionCompany(
            id=company.id,
            name=company.name,
            subscription_plan=company.subscriptionPlan or "pro",
            subscription_status="ACTIVE" if company.isActive else "SUSPENDED",
            business_type=company.businessType,
            contact_phone=company.phone,
            primary_contact_name=company.primaryContactName,
            dot_number=company.dotNumber,
            mc_number=company.mcNumber,
        )

        return AuthSessionResponse(user=session_user, company=session_company, access_token=token)

    async def verify_email(self, token: str) -> User:
        """Verify user email with token."""
        result = await self.db.execute(
            select(User).where(User.email_verification_token == token)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("Invalid or expired verification token")

        # Check if token is expired (24 hours)
        if user.email_verification_sent_at:
            if datetime.utcnow() - user.email_verification_sent_at > timedelta(hours=24):
                raise ValueError("Verification token has expired. Please request a new one.")

        user.email_verified = True
        user.email_verification_token = None

        await self._log_audit_event(
            event_type="auth.email_verified",
            action=f"Email verified: {user.email}",
            user_id=user.id,
            user_email=user.email,
            company_id=user.company_id,
        )

        await self.db.commit()
        return user

    async def resend_verification_email(self, user: User) -> None:
        """Resend verification email with new token."""
        if user.email_verified:
            raise ValueError("Email is already verified")

        user.email_verification_token = secrets.token_urlsafe(32)
        user.email_verification_sent_at = datetime.utcnow()

        await self._log_audit_event(
            event_type="auth.email_verification_sent",
            action=f"Verification email resent: {user.email}",
            user_id=user.id,
            user_email=user.email,
            company_id=user.company_id,
        )

        await self.db.commit()
        await self._send_verification_email(user)

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """Change user password with validation."""
        if not verify_password(current_password, user.hashed_password):
            await self._log_audit_event(
                event_type="auth.password_change",
                action=f"Failed password change attempt: {user.email}",
                user_id=user.id,
                user_email=user.email,
                company_id=user.company_id,
                status="failure",
            )
            raise ValueError("Current password is incorrect")

        # Validate new password
        is_valid, errors = validate_password(new_password, user.email)
        if not is_valid:
            raise ValueError(f"New password does not meet requirements: {'; '.join(errors)}")

        user.hashed_password = hash_password(new_password)
        user.must_change_password = False
        user.password_changed_at = datetime.utcnow()

        await self._log_audit_event(
            event_type="auth.password_change",
            action=f"Password changed: {user.email}",
            user_id=user.id,
            user_email=user.email,
            company_id=user.company_id,
        )

        await self.db.commit()

    async def request_password_reset(self, email: str) -> Optional[str]:
        """Generate password reset token."""
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

        if not user:
            # Don't reveal if email exists
            return None

        reset_token = secrets.token_urlsafe(32)
        # Store in email_verification_token temporarily (or create separate field)
        user.email_verification_token = f"reset:{reset_token}"
        user.email_verification_sent_at = datetime.utcnow()

        await self._log_audit_event(
            event_type="auth.password_reset",
            action=f"Password reset requested: {user.email}",
            user_id=user.id,
            user_email=user.email,
            company_id=user.company_id,
        )

        await self.db.commit()
        return reset_token

    async def _assign_default_role(self, user_id: str, role_name: str) -> None:
        """Assign a role to a user during registration."""
        result = await self.db.execute(
            select(Role)
            .where(Role.name == role_name)
            .where(Role.is_system_role == True)
            .where(Role.is_active == True)
        )
        role = result.scalar_one_or_none()

        if role:
            user_role = UserRole(user_id=user_id, role_id=role.id)
            self.db.add(user_role)
        else:
            logger.warning(f"Role {role_name} not found, using legacy role column")
            user = await self.db.get(User, user_id)
            if user:
                user.role = role_name

    async def _get_user_roles(self, user_id: str) -> List[str]:
        """Get all role names for a user."""
        result = await self.db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .where(Role.is_active == True)
        )
        return [row[0] for row in result.fetchall()]

    async def _get_driver_id_for_user(self, user_id: str) -> Optional[str]:
        """Get driver ID if user is linked to a driver profile."""
        result = await self.db.execute(
            select(Driver.id).where(Driver.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        return row if row else None

    async def _log_audit_event(
        self,
        event_type: str,
        action: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        company_id: Optional[str] = None,
        status: str = "success",
        extra_data: Optional[dict] = None,
    ) -> None:
        """Log security event to audit log."""
        audit = AuditLog(
            id=str(uuid.uuid4()),
            event_type=event_type,
            action=action,
            user_id=user_id,
            user_email=user_email,
            company_id=company_id,
            status=status,
            extra_data=extra_data,
        )
        self.db.add(audit)

    async def _send_verification_email(self, user: User) -> None:
        """Send email verification email."""
        from app.services.email import EmailService

        frontend_url = "https://app.freightopspro.com"  # TODO: Get from config
        verify_link = f"{frontend_url}/verify-email?token={user.email_verification_token}"

        # Use email service to send
        try:
            EmailService.send_password_reset(user.email, verify_link)  # Reuse template for now
            logger.info(f"Verification email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send verification email: {e}")

    def _normalize_identifier(self, value: str | None) -> str | None:
        if not value:
            return None
        trimmed = value.strip().upper()
        cleaned = "".join(char for char in trimmed if char.isalnum())
        return cleaned or None

    def _matches_company_identifier(self, verification: str, company: Company) -> bool:
        candidates = [
            self._normalize_identifier(company.dotNumber),
            self._normalize_identifier(company.mcNumber),
        ]
        return verification in [c for c in candidates if c]
