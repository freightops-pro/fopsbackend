"""Tenant-specific endpoints for the tenant app."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api import deps
from app.models.user import User


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


@router.get("/features", response_model=TenantFeatures)
async def get_tenant_features(
    current_user: User = Depends(deps.get_current_user),
) -> TenantFeatures:
    """
    Get the features enabled for the current tenant.

    Banking is disabled by default and must be explicitly enabled by HQ.
    Other features have sensible defaults for typical trucking operations.

    In the future, this will query the company's feature flags from the database.
    For now, it returns reasonable defaults.
    """
    # TODO: Query company's feature flags from database when HQ enables features
    # For now, return defaults with banking disabled
    return TenantFeatures(
        banking=False,  # Disabled by default - must be enabled by HQ
        payroll=True,
        crm=False,
        hr=True,
        fleet=True,
        dispatch=True,
        accounting=True,
    )
