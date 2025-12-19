from __future__ import annotations

import logging
import uuid
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.company import Company
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.schemas.auth import AuthSessionResponse, SessionCompany, SessionUser, UserCreate, UserLogin

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, payload: UserCreate) -> Tuple[User, str]:
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

        user = User(
            id=str(uuid.uuid4()),
            email=payload.email.lower(),
            hashed_password=hash_password(payload.password),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            company_id=company.id,
            role=None,  # Legacy field - no longer used
        )
        self.db.add(user)
        await self.db.flush()  # Get the user ID before committing

        # Assign TENANT_ADMIN role to new users
        await self._assign_default_role(user.id, "TENANT_ADMIN")

        await self.db.commit()
        await self.db.refresh(user)

        token = create_access_token({"sub": user.id})
        return user, token

    async def _assign_default_role(self, user_id: str, role_name: str) -> None:
        """Assign a role to a user during registration."""
        # Find the system role
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
            logger.info(f"Assigned role {role_name} to user {user_id}")
        else:
            # Fallback: set legacy role if RBAC tables not seeded yet
            logger.warning(f"Role {role_name} not found in RBAC tables, using legacy role column")
            user = await self.db.get(User, user_id)
            if user:
                user.role = role_name

    async def authenticate(self, payload: UserLogin) -> Tuple[User, str]:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[AUTH] Starting authentication for email: {payload.email}")
        
        logger.info(f"[AUTH] Executing user query...")
        result = await self.db.execute(select(User).where(User.email == payload.email.lower()))
        logger.info(f"[AUTH] User query completed")
        user = result.scalar_one_or_none()
        logger.info(f"[AUTH] User found: {user is not None}")
        
        if not user or not verify_password(payload.password, user.hashed_password):
            logger.warning(f"[AUTH] Invalid credentials for email: {payload.email}")
            raise ValueError("Invalid credentials")
        if not user.is_active:
            logger.warning(f"[AUTH] User disabled: {user.id}")
            raise ValueError("User disabled")

        logger.info(f"[AUTH] Fetching company: {user.company_id}")
        company = await self.db.get(Company, user.company_id)
        logger.info(f"[AUTH] Company found: {company is not None}")
        if not company:
            logger.error(f"[AUTH] Company not found for user: {user.id}")
            raise ValueError("Company not found for user")

        logger.info(f"[AUTH] Verifying code...")
        verification_code = self._normalize_identifier(payload.verification_code)
        if not verification_code:
            logger.warning(f"[AUTH] Verification code is empty")
            raise ValueError("USDOT or MC number is required for verification")
        if not self._matches_company_identifier(verification_code, company):
            logger.warning(f"[AUTH] Verification code mismatch for user: {user.id}")
            raise ValueError("Unable to verify USDOT/MC credentials for this account")

        logger.info(f"[AUTH] Creating access token...")
        access_token = create_access_token({"sub": user.id})
        logger.info(f"[AUTH] Authentication successful for user: {user.id}")
        return user, access_token

    async def build_session(self, user: User, token: str | None = None) -> AuthSessionResponse:
        company = await self.db.get(Company, user.company_id)
        if not company:
            raise ValueError("Company not found for user")

        # Get roles from RBAC tables
        roles = await self._get_user_roles(user.id)

        # Fallback to legacy role if no roles found
        if not roles and user.role:
            roles = [user.role.upper()]

        # Default to TENANT_ADMIN if still no roles (shouldn't happen)
        if not roles:
            roles = ["TENANT_ADMIN"]

        session_user = SessionUser(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            roles=roles,
            must_change_password=user.must_change_password,
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

    async def _get_user_roles(self, user_id: str) -> List[str]:
        """Get all role names for a user from the RBAC tables."""
        result = await self.db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .where(Role.is_active == True)
        )
        return [row[0] for row in result.fetchall()]

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
        return verification in [candidate for candidate in candidates if candidate]

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """Change user password and clear must_change_password flag."""
        if not verify_password(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")

        user.hashed_password = hash_password(new_password)
        user.must_change_password = False
        await self.db.commit()

