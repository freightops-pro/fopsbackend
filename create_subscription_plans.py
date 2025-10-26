#!/usr/bin/env python3
"""
Create default subscription plans
Run this script to create the initial subscription plans
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from sqlalchemy.orm import Session
from app.config.db import engine, Base, create_tables
from app.models.stripeModels import SubscriptionPlan
from decimal import Decimal

def create_default_plans():
    """Create default subscription plans"""
    # Create tables if they don't exist
    create_tables()
    
    with Session(engine) as db:
        # Check if plans already exist
        existing_plan = db.query(SubscriptionPlan).first()
        if existing_plan:
            print("Subscription plans already exist. Skipping creation.")
            return
        
        # Create default plans
        plans = [
            {
                "id": "plan_starter",
                "name": "Starter",
                "stripe_price_id": "price_starter_monthly",  # Replace with actual Stripe price ID
                "description": "Perfect for small trucking companies getting started",
                "price_monthly": Decimal("99.00"),
                "price_yearly": Decimal("990.00"),  # 2 months free
                "interval": "month",
                "features": [
                    "Up to 5 users",
                    "Up to 10 vehicles",
                    "Basic dispatch management",
                    "Driver mobile app",
                    "Basic reporting",
                    "Email support"
                ],
                "max_users": 5,
                "max_vehicles": 10,
                "is_popular": False,
                "sort_order": 1
            },
            {
                "id": "plan_professional",
                "name": "Professional",
                "stripe_price_id": "price_professional_monthly",  # Replace with actual Stripe price ID
                "description": "Ideal for growing trucking companies",
                "price_monthly": Decimal("199.00"),
                "price_yearly": Decimal("1990.00"),  # 2 months free
                "interval": "month",
                "features": [
                    "Up to 25 users",
                    "Up to 50 vehicles",
                    "Advanced dispatch management",
                    "Driver mobile app",
                    "Advanced reporting & analytics",
                    "Priority support",
                    "API access",
                    "Custom integrations",
                    "Real-time collaboration",
                    "Advanced annotations & comments"
                ],
                "max_users": 25,
                "max_vehicles": 50,
                "is_popular": True,
                "sort_order": 2
            },
            {
                "id": "plan_enterprise",
                "name": "Enterprise",
                "stripe_price_id": "price_enterprise_monthly",  # Replace with actual Stripe price ID
                "description": "For large trucking companies with complex needs",
                "price_monthly": Decimal("399.00"),
                "price_yearly": Decimal("3990.00"),  # 2 months free
                "interval": "month",
                "features": [
                    "Unlimited users",
                    "Unlimited vehicles",
                    "Enterprise dispatch management",
                    "Driver mobile app",
                    "Advanced reporting & analytics",
                    "Dedicated support",
                    "Full API access",
                    "Custom integrations",
                    "White-label options",
                    "Custom training",
                    "SLA guarantee",
                    "Real-time collaboration",
                    "Advanced annotations & comments",
                    "Internal team messaging",
                    "Team chat rooms",
                    "Group collaboration tools"
                ],
                "max_users": None,  # Unlimited
                "max_vehicles": None,  # Unlimited
                "is_popular": False,
                "sort_order": 3
            }
        ]
        
        for plan_data in plans:
            plan = SubscriptionPlan(**plan_data)
            db.add(plan)
        
        db.commit()
        
        print("✅ Default subscription plans created successfully!")
        print("\nPlans created:")
        for plan_data in plans:
            print(f"- {plan_data['name']}: ${plan_data['price_monthly']}/month")
        print("\n⚠️  IMPORTANT: Update the stripe_price_id values with actual Stripe price IDs!")

if __name__ == "__main__":
    create_default_plans()
