"""Tenant-specific endpoints for the tenant app."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api import deps
from app.core.db import get_db
from app.models.user import User
from app.models.billing import Subscription, SubscriptionAddOn
from app.models.integration import CompanyIntegration, Integration


router = APIRouter()


class TenantFeatures(BaseModel):
    """Features enabled for the current tenant."""
    banking: bool = False
    payroll: bool = True
    crm: bool = False
    hr: bool = True
    fleet: bool = True
    dispatch: bool = True
    accounting: bool = True
    port_integration: bool = False
    ai_employees: bool = True


@router.get("/features", response_model=TenantFeatures)
async def get_tenant_features(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantFeatures:
    """
    Get the features enabled for the current tenant.

    Features are determined by:
    1. Subscription status (active subscription required for most features)
    2. Active add-ons (port_integration, check_payroll)
    3. Connected integrations (banking via Synctera)
    4. Subscription plan tier

    Banking is disabled by default and requires Synctera KYB approval.
    """
    company_id = current_user.company_id

    # Default features based on typical trucking operations
    features = TenantFeatures(
        banking=False,
        payroll=True,
        crm=False,
        hr=True,
        fleet=True,
        dispatch=True,
        accounting=True,
        port_integration=False,
        ai_employees=True,
    )

    # Check subscription and add-ons
    sub_result = await db.execute(
        select(Subscription)
        .options(joinedload(Subscription.add_ons))
        .where(Subscription.company_id == company_id)
    )
    subscription = sub_result.scalar_one_or_none()

    if subscription:
        # Check for active add-ons
        for addon in subscription.add_ons or []:
            if addon.status == "active":
                if addon.service == "port_integration":
                    features.port_integration = True
                elif addon.service == "check_payroll":
                    # Check payroll enhances payroll features
                    features.payroll = True

        # Premium features based on subscription plan
        if subscription.subscription_type == "contract":
            features.crm = True  # CRM available for contract customers

    # Check for active banking integration (Synctera)
    banking_result = await db.execute(
        select(CompanyIntegration)
        .join(Integration)
        .where(
            CompanyIntegration.company_id == company_id,
            Integration.integration_key == "synctera",
            CompanyIntegration.status == "active",
        )
    )
    banking_integration = banking_result.scalar_one_or_none()

    if banking_integration:
        # Check if KYB is approved
        credentials = banking_integration.credentials or {}
        kyb_status = credentials.get("kyb_status")
        if kyb_status == "approved":
            features.banking = True

    return features
