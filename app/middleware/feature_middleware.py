from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Callable, Any
from functools import wraps

from app.config.db import get_db
from app.services.feature_service import FeatureService, get_feature_service


def require_feature(feature_name: str):
    """
    Decorator/dependency to require a specific feature for route access.
    Raises 403 if company doesn't have access to the feature.
    """
    def feature_checker(company_id: str, feature_service: FeatureService = Depends(get_feature_service)):
        feature_service.require_feature_access(company_id, feature_name)
        return True
    
    return feature_checker


def require_subscription_tier(required_tiers: list):
    """
    Decorator/dependency to require specific subscription tiers for route access.
    """
    def tier_checker(company_id: str, feature_service: FeatureService = Depends(get_feature_service)):
        tier_info = feature_service.get_subscription_tier_info(company_id)
        
        if not tier_info['tier'] or tier_info['tier'] not in required_tiers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Insufficient subscription tier",
                    "required_tiers": required_tiers,
                    "current_tier": tier_info['tier'],
                    "action": "upgrade_required" if tier_info['is_self_service'] else "contact_sales"
                }
            )
        
        return tier_info
    
    return tier_checker


def require_professional_or_enterprise():
    """Shortcut for routes that need Professional or Enterprise tier"""
    return require_subscription_tier(['plan_professional', 'plan_enterprise'])


def require_enterprise_only():
    """Shortcut for routes that need Enterprise tier only"""
    return require_subscription_tier(['plan_enterprise'])


class FeatureGate:
    """
    Context manager for feature gating in route handlers
    """
    def __init__(self, feature_service: FeatureService, company_id: str, feature_name: str):
        self.feature_service = feature_service
        self.company_id = company_id
        self.feature_name = feature_name
    
    def __enter__(self):
        self.feature_service.require_feature_access(self.company_id, self.feature_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def create_feature_gate(feature_service: FeatureService, company_id: str, feature_name: str) -> FeatureGate:
    """Helper to create a feature gate"""
    return FeatureGate(feature_service, company_id, feature_name)
