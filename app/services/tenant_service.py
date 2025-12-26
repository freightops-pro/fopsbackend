"""
Tenant Service for HQ admin tenant management.

Provides:
- Listing all tenants with filtering
- Tenant details and stats
- Tenant status management (suspend/activate)
- Platform-wide statistics
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.company import Company
from app.models.user import User
from app.models.driver import Driver
from app.models.load import Load
from app.models.audit_log import AuditLog
from app.models.rbac import UserRole, Role
from app.schemas.tenant import (
    TenantResponse,
    TenantDetailResponse,
    TenantListResponse,
    TenantFilter,
    TenantUserResponse,
    TenantUsersListResponse,
    PlatformStats,
)

logger = logging.getLogger(__name__)


class TenantService:
    """Service for HQ admin tenant management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tenants(
        self,
        filters: Optional[TenantFilter] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> TenantListResponse:
        """
        List all tenants with filtering and pagination.

        HQ admin only.
        """
        query = select(Company)
        count_query = select(func.count(Company.id))

        # Apply filters
        if filters:
            if filters.search:
                search_term = f"%{filters.search}%"
                search_condition = or_(
                    Company.name.ilike(search_term),
                    Company.email.ilike(search_term),
                    Company.dotNumber.ilike(search_term),
                    Company.mcNumber.ilike(search_term),
                )
                query = query.where(search_condition)
                count_query = count_query.where(search_condition)

            if filters.is_active is not None:
                query = query.where(Company.is_active == filters.is_active)
                count_query = count_query.where(Company.is_active == filters.is_active)

            if filters.subscription_plan:
                query = query.where(Company.subscription_plan == filters.subscription_plan)
                count_query = count_query.where(Company.subscription_plan == filters.subscription_plan)

            if filters.state:
                query = query.where(Company.state == filters.state)
                count_query = count_query.where(Company.state == filters.state)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(desc(Company.created_at)).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        companies = result.scalars().all()

        # Get counts for each tenant
        items = []
        for company in companies:
            tenant = await self._to_response(company)
            items.append(tenant)

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return TenantListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_tenant(self, tenant_id: str) -> Optional[TenantDetailResponse]:
        """Get detailed tenant information."""
        company = await self.db.get(Company, tenant_id)
        if not company:
            return None

        return await self._to_detail_response(company)

    async def get_tenant_users(self, tenant_id: str) -> TenantUsersListResponse:
        """Get all users for a tenant."""
        result = await self.db.execute(
            select(User)
            .where(User.company_id == tenant_id)
            .order_by(User.created_at.desc())
        )
        users = result.scalars().all()

        items = []
        for user in users:
            # Get roles
            roles_result = await self.db.execute(
                select(Role)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id)
            )
            roles = [r.name for r in roles_result.scalars().all()]

            items.append(TenantUserResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                is_active=user.is_active,
                roles=roles,
                last_login=user.last_login_at,
                created_at=user.created_at,
            ))

        return TenantUsersListResponse(
            items=items,
            total=len(items),
        )

    async def update_tenant_status(
        self,
        tenant_id: str,
        is_active: bool,
        reason: Optional[str] = None,
        admin_user_id: Optional[str] = None,
    ) -> Optional[TenantDetailResponse]:
        """Suspend or activate a tenant."""
        company = await self.db.get(Company, tenant_id)
        if not company:
            return None

        company.is_active = is_active
        await self.db.commit()
        await self.db.refresh(company)

        # Log the action
        logger.info(
            f"Tenant {tenant_id} {'activated' if is_active else 'suspended'} "
            f"by admin {admin_user_id}. Reason: {reason}"
        )

        return await self._to_detail_response(company)

    async def get_platform_stats(self) -> PlatformStats:
        """Get platform-wide statistics."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Total tenants
        total_result = await self.db.execute(select(func.count(Company.id)))
        total_tenants = total_result.scalar() or 0

        # Active tenants
        active_result = await self.db.execute(
            select(func.count(Company.id)).where(Company.is_active == True)
        )
        active_tenants = active_result.scalar() or 0

        # Total users
        users_result = await self.db.execute(select(func.count(User.id)))
        total_users = users_result.scalar() or 0

        # Total drivers
        drivers_result = await self.db.execute(select(func.count(Driver.id)))
        total_drivers = drivers_result.scalar() or 0

        # New tenants this month
        new_result = await self.db.execute(
            select(func.count(Company.id)).where(Company.created_at >= month_start)
        )
        new_tenants = new_result.scalar() or 0

        # Tenants by subscription plan
        plan_result = await self.db.execute(
            select(Company.subscription_plan, func.count(Company.id))
            .group_by(Company.subscription_plan)
        )
        tenants_by_plan = {
            row[0] or "none": row[1]
            for row in plan_result.fetchall()
        }

        # Tenants by state
        state_result = await self.db.execute(
            select(Company.state, func.count(Company.id))
            .where(Company.state.isnot(None))
            .group_by(Company.state)
            .order_by(desc(func.count(Company.id)))
            .limit(10)
        )
        tenants_by_state = {
            row[0]: row[1]
            for row in state_result.fetchall()
        }

        # Total loads this month (if Load model exists)
        try:
            loads_result = await self.db.execute(
                select(func.count(Load.id)).where(Load.created_at >= month_start)
            )
            total_loads = loads_result.scalar() or 0
        except Exception:
            total_loads = 0

        return PlatformStats(
            total_tenants=total_tenants,
            active_tenants=active_tenants,
            inactive_tenants=total_tenants - active_tenants,
            total_users=total_users,
            total_drivers=total_drivers,
            total_loads_this_month=total_loads,
            new_tenants_this_month=new_tenants,
            tenants_by_plan=tenants_by_plan,
            tenants_by_state=tenants_by_state,
        )

    async def _to_response(self, company: Company) -> TenantResponse:
        """Convert company to tenant response with counts."""
        # Get user count
        user_count_result = await self.db.execute(
            select(func.count(User.id)).where(User.company_id == company.id)
        )
        user_count = user_count_result.scalar() or 0

        # Get driver count
        driver_count_result = await self.db.execute(
            select(func.count(Driver.id)).where(Driver.company_id == company.id)
        )
        driver_count = driver_count_result.scalar() or 0

        # Get last activity (most recent audit log)
        last_activity_result = await self.db.execute(
            select(AuditLog.timestamp)
            .where(AuditLog.company_id == company.id)
            .order_by(desc(AuditLog.timestamp))
            .limit(1)
        )
        last_activity = last_activity_result.scalar()

        return TenantResponse(
            id=company.id,
            name=company.name,
            legal_name=company.legal_name,
            email=company.email,
            phone=company.phone,
            subscription_plan=company.subscription_plan,
            is_active=company.is_active,
            dot_number=company.dotNumber,
            mc_number=company.mcNumber,
            city=company.city,
            state=company.state,
            created_at=company.created_at,
            user_count=user_count,
            driver_count=driver_count,
            last_activity=last_activity,
        )

    async def _to_detail_response(self, company: Company) -> TenantDetailResponse:
        """Convert company to detailed tenant response."""
        base = await self._to_response(company)

        # Get recent login count (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        logins_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.company_id == company.id,
                    AuditLog.event_type == "auth.login_success",
                    AuditLog.timestamp >= week_ago,
                )
            )
        )
        recent_logins = logins_result.scalar() or 0

        return TenantDetailResponse(
            **base.model_dump(),
            business_type=company.business_type,
            tax_id=company.tax_id,
            website=company.website,
            address_line1=company.address_line1,
            address_line2=company.address_line2,
            zip_code=company.zip_code,
            primary_contact_name=company.primary_contact_name,
            banking_enabled=False,  # TODO: Check banking status
            kyb_status=None,  # TODO: Get from banking service
            subscription_status=company.subscription_status if hasattr(company, 'subscription_status') else None,
            integrations_count=0,  # TODO: Count integrations
            recent_logins=recent_logins,
        )
