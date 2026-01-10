"""
Set Perpetual Subscription for Demo User

This script updates the demo company subscription to never expire
by setting the subscription end date 100 years in the future.

Run: python -m scripts.utilities.set_perpetual_subscription
"""

# Set up Windows-compatible event loop BEFORE any database imports
import sys
if sys.platform == "win32":
    import asyncio
    import selectors
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionFactory
from app.models.company import Company
from app.models.user import User
from app.models.billing import Subscription, SubscriptionAddOn


async def set_perpetual_subscription(email: str = "owner@demofreight.com"):
    """Set perpetual subscription for a user's company."""

    async with AsyncSessionFactory() as db:
        # Find the user
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"ERROR User not found: {email}")
            return

        print(f"OK Found user: {user.first_name} {user.last_name} ({email})")

        # Get the company
        result = await db.execute(
            select(Company).where(Company.id == user.company_id)
        )
        company = result.scalar_one_or_none()

        if not company:
            print(f"ERROR Company not found for user")
            return

        print(f"OK Found company: {company.name}")

        # Get or create subscription
        result = await db.execute(
            select(Subscription).where(Subscription.company_id == company.id)
        )
        subscription = result.scalar_one_or_none()

        # Set dates 100 years in the future for "perpetual" access
        far_future = datetime.utcnow() + timedelta(days=36500)  # ~100 years

        if subscription:
            # Update existing subscription
            subscription.status = "active"
            subscription.trial_ends_at = far_future
            subscription.current_period_end = far_future
            subscription.cancel_at_period_end = False
            subscription.canceled_at = None
            subscription.subscription_type = "contract"  # Mark as contract for special handling

            # Set metadata to indicate perpetual
            subscription.metadata_json = subscription.metadata_json or {}
            subscription.metadata_json["perpetual"] = True
            subscription.metadata_json["note"] = "Development/demo account with perpetual access"

            print(f"OK Updated subscription ID: {subscription.id}")
        else:
            # Create new subscription
            subscription = Subscription(
                id=f"sub_perpetual_{company.id[:8]}",
                company_id=company.id,
                status="active",
                subscription_type="contract",
                billing_cycle="annual",
                truck_count=999,
                base_price_per_truck=0.00,
                total_monthly_cost=0.00,
                trial_ends_at=far_future,
                current_period_start=datetime.utcnow(),
                current_period_end=far_future,
                cancel_at_period_end=False,
                metadata_json={
                    "perpetual": True,
                    "note": "Development/demo account with perpetual access"
                }
            )
            db.add(subscription)
            print(f"OK Created new subscription ID: {subscription.id}")

        await db.commit()

        # Add or activate add-ons
        print(f"\nOK Setting up add-ons...")

        # Port Integration Add-on
        result = await db.execute(
            select(SubscriptionAddOn).where(
                SubscriptionAddOn.subscription_id == subscription.id,
                SubscriptionAddOn.service == "port_integration"
            )
        )
        port_addon = result.scalar_one_or_none()

        if not port_addon:
            port_addon = SubscriptionAddOn(
                id=f"addon_port_{company.id[:8]}",
                subscription_id=subscription.id,
                service="port_integration",
                name="Port Integration",
                description="Access to port booking and container tracking integrations",
                status="active",
                monthly_cost=0.00,
                has_trial=False,
                activated_at=datetime.utcnow(),
                metadata_json={"perpetual": True}
            )
            db.add(port_addon)
            print(f"   OK Created Port Integration add-on")
        else:
            port_addon.status = "active"
            port_addon.monthly_cost = 0.00
            port_addon.activated_at = datetime.utcnow()
            print(f"   OK Activated Port Integration add-on")

        # Check Payroll (HR) Add-on
        result = await db.execute(
            select(SubscriptionAddOn).where(
                SubscriptionAddOn.subscription_id == subscription.id,
                SubscriptionAddOn.service == "check_payroll"
            )
        )
        hr_addon = result.scalar_one_or_none()

        if not hr_addon:
            hr_addon = SubscriptionAddOn(
                id=f"addon_hr_{company.id[:8]}",
                subscription_id=subscription.id,
                service="check_payroll",
                name="Check Payroll",
                description="HR and payroll management integration",
                status="active",
                monthly_cost=0.00,
                employee_count=999,
                per_employee_cost=0.00,
                has_trial=False,
                activated_at=datetime.utcnow(),
                metadata_json={"perpetual": True}
            )
            db.add(hr_addon)
            print(f"   OK Created Check Payroll (HR) add-on")
        else:
            hr_addon.status = "active"
            hr_addon.monthly_cost = 0.00
            hr_addon.employee_count = 999
            hr_addon.per_employee_cost = 0.00
            hr_addon.activated_at = datetime.utcnow()
            print(f"   OK Activated Check Payroll (HR) add-on")

        await db.commit()

        print(f"\nSUCCESS Subscription set to PERPETUAL")
        print(f"   Status: {subscription.status}")
        print(f"   Type: {subscription.subscription_type}")
        print(f"   Period End: {subscription.current_period_end.strftime('%Y-%m-%d')} (~100 years)")
        print(f"   Trial Ends: {subscription.trial_ends_at.strftime('%Y-%m-%d') if subscription.trial_ends_at else 'N/A'}")
        print(f"   Monthly Cost: ${subscription.total_monthly_cost}")
        print(f"   Truck Count: {subscription.truck_count}")
        print(f"\n   Add-ons:")
        print(f"     - Port Integration: active")
        print(f"     - Check Payroll (HR): active (999 employees)")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("SET PERPETUAL SUBSCRIPTION")
    print("=" * 60)
    print()

    # Default to demo user, but can be changed
    email = "owner@demofreight.com"

    # Allow command line argument
    if len(sys.argv) > 1:
        email = sys.argv[1]

    await set_perpetual_subscription(email)

    print()
    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    if sys.platform == "win32":
        # Use the selector event loop for Windows
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    else:
        asyncio.run(main())
