from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from app.models.stripeModels import CompanySubscription, SubscriptionPlan
from app.models.userModels import Companies


class FeatureService:
    """Service to check feature access based on subscription tier"""
    
    # Define which features are available to which subscription tiers
    FEATURE_TIERS = {
        'collaboration': ['plan_professional', 'plan_enterprise'],
        'internal_messaging': ['plan_enterprise'],
        'api_access': ['plan_professional', 'plan_enterprise'],
        'advanced_reporting': ['plan_professional', 'plan_enterprise'],
        'custom_integrations': ['plan_professional', 'plan_enterprise'],
        'priority_support': ['plan_professional', 'plan_enterprise'],
        'white_label': ['plan_enterprise'],
        'dedicated_support': ['plan_enterprise'],
        'sla_guarantee': ['plan_enterprise']
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_company_subscription_tier(self, company_id: str) -> Optional[str]:
        """Get the subscription plan ID for a company"""
        subscription = self.db.query(CompanySubscription).join(SubscriptionPlan).filter(
            CompanySubscription.company_id == company_id,
            CompanySubscription.status == 'active'
        ).first()
        
        if subscription:
            return subscription.plan_id
        
        return None
    
    def can_access_feature(self, company_id: str, feature_name: str) -> bool:
        """Check if a company can access a specific feature"""
        if feature_name not in self.FEATURE_TIERS:
            # Unknown feature - default to false for security
            return False
        
        # Get company's subscription tier
        subscription_tier = self.get_company_subscription_tier(company_id)
        
        if not subscription_tier:
            # No active subscription - only basic features
            return False
        
        # Check if the subscription tier allows this feature
        allowed_tiers = self.FEATURE_TIERS[feature_name]
        return subscription_tier in allowed_tiers
    
    def get_available_features(self, company_id: str) -> List[str]:
        """Get all features available to a company based on their subscription"""
        subscription_tier = self.get_company_subscription_tier(company_id)
        
        if not subscription_tier:
            return []
        
        available_features = []
        for feature_name, allowed_tiers in self.FEATURE_TIERS.items():
            if subscription_tier in allowed_tiers:
                available_features.append(feature_name)
        
        return available_features
    
    def get_subscription_tier_info(self, company_id: str) -> Dict:
        """Get detailed subscription tier information for a company"""
        subscription = self.db.query(CompanySubscription).join(SubscriptionPlan).filter(
            CompanySubscription.company_id == company_id,
            CompanySubscription.status == 'active'
        ).first()
        
        if not subscription:
            return {
                'tier': None,
                'plan_name': 'No Active Subscription',
                'features': [],
                'is_self_service': False
            }
        
        available_features = self.get_available_features(company_id)
        
        # Determine if this is a self-service or custom tier
        is_self_service = subscription.plan_id in ['plan_starter', 'plan_professional']
        
        return {
            'tier': subscription.plan_id,
            'plan_name': subscription.plan.name,
            'features': available_features,
            'is_self_service': is_self_service,
            'subscription_id': subscription.id,
            'status': subscription.status
        }
    
    def require_feature_access(self, company_id: str, feature_name: str):
        """Raise HTTPException if company doesn't have access to feature"""
        if not self.can_access_feature(company_id, feature_name):
            tier_info = self.get_subscription_tier_info(company_id)
            
            if tier_info['tier'] == 'plan_starter':
                # Starter tier - can upgrade via Stripe
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "Feature not available in current plan",
                        "feature": feature_name,
                        "current_plan": tier_info['plan_name'],
                        "action": "upgrade_required",
                        "message": f"This feature requires a Professional or Enterprise subscription. Please upgrade your plan."
                    }
                )
            elif tier_info['tier'] == 'plan_professional':
                # Professional tier but missing specific feature - should not happen normally
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "Feature not available in current plan",
                        "feature": feature_name,
                        "current_plan": tier_info['plan_name'],
                        "action": "upgrade_required",
                        "message": f"This feature requires an Enterprise subscription. Please upgrade your plan."
                    }
                )
            else:
                # Enterprise tier - need to contact sales for custom features
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "Feature not available in current plan",
                        "feature": feature_name,
                        "current_plan": tier_info['plan_name'],
                        "action": "contact_sales",
                        "message": f"This feature requires a custom Enterprise subscription. Please contact our sales team."
                    }
                )


def get_feature_service(db: Session) -> FeatureService:
    """Dependency to get FeatureService instance"""
    return FeatureService(db)
