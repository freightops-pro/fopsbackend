from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from decimal import Decimal
import uuid

from app.models.port import CompanyPortAddon, PortAPIUsage, PortAddonPricing
from app.services.stripe_service import StripeService
from app.config.logging_config import get_logger

logger = get_logger(__name__)

# Operation pricing (in USD)
OPERATION_COSTS = {
    "track_container": Decimal("0.50"),
    "vessel_schedule": Decimal("1.00"),
    "gate_status": Decimal("1.50"),
    "document_upload": Decimal("2.00"),
    "berth_availability": Decimal("0.75")
}

MONTHLY_UNLIMITED_PRICE = Decimal("99.00")
BREAKEVEN_REQUESTS = 132  # $99 / $0.75 average

class PortBillingService:
    """
    Manages port add-on billing and usage tracking
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.stripe_service = StripeService(db)
    
    def enable_port_addon(
        self,
        company_id: str,
        pricing_model: PortAddonPricing,
        auto_optimize: bool = False
    ) -> CompanyPortAddon:
        """Enable port credentials add-on for company"""
        
        # Check if already exists
        existing = self.db.query(CompanyPortAddon).filter(
            CompanyPortAddon.company_id == company_id
        ).first()
        
        if existing:
            raise ValueError("Port add-on already enabled")
        
        addon = CompanyPortAddon(
            id=str(uuid.uuid4()),
            company_id=company_id,
            pricing_model=pricing_model,
            current_month=datetime.utcnow().strftime("%Y-%m"),
            auto_optimize=auto_optimize,
            is_active=True
        )
        
        if pricing_model == PortAddonPricing.UNLIMITED_MONTHLY:
            addon.monthly_price = MONTHLY_UNLIMITED_PRICE
            addon.subscription_start = datetime.utcnow()
            addon.subscription_end = datetime.utcnow() + timedelta(days=30)
            addon.next_billing_date = addon.subscription_end
            
            # TODO: Create Stripe subscription
            # addon.stripe_subscription_id = self.stripe_service.create_port_addon_subscription(company_id)
        
        self.db.add(addon)
        self.db.commit()
        self.db.refresh(addon)
        
        logger.info(f"Port add-on enabled: {pricing_model.value}", extra={
            "extra_fields": {"company_id": company_id}
        })
        
        return addon
    
    def record_api_usage(
        self,
        company_id: str,
        port_code: str,
        operation: str,
        user_id: Optional[str] = None,
        request_params: Optional[Dict] = None,
        response_time_ms: Optional[int] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> PortAPIUsage:
        """Record individual API usage"""
        
        addon = self.db.query(CompanyPortAddon).filter(
            CompanyPortAddon.company_id == company_id,
            CompanyPortAddon.is_active == True
        ).first()
        
        if not addon:
            raise ValueError("Port add-on not enabled")
        
        # Get operation cost
        operation_cost = OPERATION_COSTS.get(operation, Decimal("0.75"))
        
        # Create usage record
        usage = PortAPIUsage(
            id=str(uuid.uuid4()),
            company_id=company_id,
            port_code=port_code,
            operation=operation,
            operation_cost=operation_cost,
            request_params=request_params,
            response_time_ms=response_time_ms,
            status=status,
            error_message=error_message,
            billing_month=datetime.utcnow().strftime("%Y-%m"),
            user_id=user_id
        )
        
        self.db.add(usage)
        
        # Update addon totals (only for pay-per-request)
        if addon.pricing_model == PortAddonPricing.PAY_PER_REQUEST:
            addon.current_month_requests += 1
            addon.current_month_cost += operation_cost
        
        self.db.commit()
        
        # Check if auto-optimize enabled
        if addon.auto_optimize:
            self._check_optimization(addon)
        
        return usage
    
    def get_usage_stats(
        self,
        company_id: str,
        months: int = 3
    ) -> Dict[str, Any]:
        """Get usage statistics for billing analysis"""
        
        addon = self.db.query(CompanyPortAddon).filter(
            CompanyPortAddon.company_id == company_id
        ).first()
        
        if not addon:
            return {"enabled": False}
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)
        
        # Get usage history
        usage_records = self.db.query(PortAPIUsage).filter(
            PortAPIUsage.company_id == company_id,
            PortAPIUsage.timestamp >= start_date
        ).all()
        
        # Group by month
        monthly_stats = {}
        for record in usage_records:
            month = record.billing_month
            if month not in monthly_stats:
                monthly_stats[month] = {
                    "requests": 0,
                    "cost": Decimal("0.00"),
                    "operations": {}
                }
            
            monthly_stats[month]["requests"] += 1
            monthly_stats[month]["cost"] += record.operation_cost
            
            op = record.operation
            if op not in monthly_stats[month]["operations"]:
                monthly_stats[month]["operations"][op] = 0
            monthly_stats[month]["operations"][op] += 1
        
        # Calculate averages
        if monthly_stats:
            avg_requests = sum(m["requests"] for m in monthly_stats.values()) / len(monthly_stats)
            avg_cost = sum(m["cost"] for m in monthly_stats.values()) / len(monthly_stats)
        else:
            avg_requests = 0
            avg_cost = Decimal("0.00")
        
        # Recommendation
        recommendation = self._get_pricing_recommendation(avg_requests, avg_cost)
        
        return {
            "enabled": True,
            "current_model": addon.pricing_model.value,
            "current_month": {
                "requests": addon.current_month_requests,
                "cost": float(addon.current_month_cost)
            },
            "monthly_stats": {
                month: {
                    "requests": stats["requests"],
                    "cost": float(stats["cost"]),
                    "operations": stats["operations"]
                }
                for month, stats in monthly_stats.items()
            },
            "averages": {
                "requests_per_month": int(avg_requests),
                "cost_per_month": float(avg_cost)
            },
            "recommendation": recommendation
        }
    
    def _get_pricing_recommendation(
        self,
        avg_requests: float,
        avg_cost: Decimal
    ) -> Dict[str, Any]:
        """Calculate optimal pricing recommendation"""
        
        pay_per_request_cost = float(avg_cost)
        unlimited_cost = float(MONTHLY_UNLIMITED_PRICE)
        
        if avg_requests < BREAKEVEN_REQUESTS:
            return {
                "recommended": "pay_per_request",
                "reason": "Low volume - pay-as-you-go is more cost-effective",
                "estimated_savings": unlimited_cost - pay_per_request_cost,
                "breakeven_at": BREAKEVEN_REQUESTS
            }
        else:
            return {
                "recommended": "unlimited_monthly",
                "reason": "High volume - unlimited plan saves money",
                "estimated_savings": pay_per_request_cost - unlimited_cost,
                "breakeven_at": BREAKEVEN_REQUESTS
            }
    
    def _check_optimization(self, addon: CompanyPortAddon):
        """Check if pricing should be auto-optimized"""
        
        # Only check once per day
        if addon.last_optimization_check:
            if (datetime.utcnow() - addon.last_optimization_check).days < 1:
                return
        
        # Get usage stats
        stats = self.get_usage_stats(addon.company_id, months=2)
        recommendation = stats["recommendation"]
        
        # If current model doesn't match recommendation for 2+ months, switch
        if recommendation["recommended"] != addon.pricing_model.value:
            if recommendation["estimated_savings"] > 50:  # Significant savings
                self.switch_pricing_model(
                    addon.company_id,
                    PortAddonPricing(recommendation["recommended"])
                )
        
        addon.last_optimization_check = datetime.utcnow()
        self.db.commit()
    
    def switch_pricing_model(
        self,
        company_id: str,
        new_model: PortAddonPricing
    ) -> CompanyPortAddon:
        """Switch between pay-per-request and unlimited"""
        
        addon = self.db.query(CompanyPortAddon).filter(
            CompanyPortAddon.company_id == company_id
        ).first()
        
        if not addon:
            raise ValueError("Port add-on not found")
        
        old_model = addon.pricing_model
        addon.pricing_model = new_model
        
        if new_model == PortAddonPricing.UNLIMITED_MONTHLY:
            addon.monthly_price = MONTHLY_UNLIMITED_PRICE
            addon.subscription_start = datetime.utcnow()
            addon.subscription_end = datetime.utcnow() + timedelta(days=30)
            # TODO: Create Stripe subscription
        else:
            # Cancel Stripe subscription if exists
            if addon.stripe_subscription_id:
                # self.stripe_service.cancel_subscription(addon.stripe_subscription_id)
                addon.stripe_subscription_id = None
        
        self.db.commit()
        
        logger.info(f"Pricing model switched: {old_model.value} → {new_model.value}", extra={
            "extra_fields": {"company_id": company_id}
        })
        
        return addon
    
    def disable_port_addon(self, company_id: str) -> bool:
        """Disable port add-on for company"""
        addon = self.db.query(CompanyPortAddon).filter(
            CompanyPortAddon.company_id == company_id
        ).first()
        
        if not addon:
            return False
        
        addon.is_active = False
        
        # Cancel Stripe subscription if exists
        if addon.stripe_subscription_id:
            # TODO: Cancel Stripe subscription
            # self.stripe_service.cancel_subscription(addon.stripe_subscription_id)
            addon.stripe_subscription_id = None
        
        self.db.commit()
        
        logger.info(f"Port add-on disabled for company {company_id}")
        return True









