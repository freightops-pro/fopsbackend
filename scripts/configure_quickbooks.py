"""
Script to configure QuickBooks Online integration credentials.

This script helps you securely configure QuickBooks OAuth credentials.
Credentials should be stored encrypted in the database via the CompanyIntegration model.

Usage:
    python -m app.scripts.configure_quickbooks --company-id <company_id> --client-id <client_id> --client-secret <client_secret>

Or use the API endpoint:
    POST /api/integrations/company
    {
        "integration_id": "quickbooks-online",
        "credentials": {
            "client_id": "ABBebmkRwW2gUN6eiW4z1UIJz8OszSXflqksfQh5J2enkUZyDw",
            "client_secret": "OsUoX77TKVMCZCTK6eyCzbpabdUm2oAizwzkh0cR"
        }
    }
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.db import get_db
from app.models.integration import CompanyIntegration, Integration


async def configure_quickbooks(
    company_id: str,
    client_id: str,
    client_secret: str,
    sandbox: bool = True,
):
    """
    Configure QuickBooks integration for a company.

    Args:
        company_id: Company ID
        client_id: QuickBooks OAuth Client ID
        client_secret: QuickBooks OAuth Client Secret
        sandbox: Whether to use sandbox environment (default: True)
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Find QuickBooks integration
        result = await session.execute(
            select(Integration).where(Integration.integration_key == "quickbooks")
        )
        integration = result.scalar_one_or_none()

        if not integration:
            print("ERROR: QuickBooks integration not found in catalog.")
            print("Please run the migration first: alembic upgrade head")
            return

        # Check if company integration already exists
        result = await session.execute(
            select(CompanyIntegration).where(
                CompanyIntegration.company_id == company_id,
                CompanyIntegration.integration_id == integration.id,
            )
        )
        company_integration = result.scalar_one_or_none()

        if company_integration:
            # Update existing
            company_integration.credentials = {
                "client_id": client_id,
                "client_secret": client_secret,
            }
            company_integration.config = {"sandbox": sandbox}
            company_integration.status = "pending"  # Will be "active" after OAuth
            print(f"Updated QuickBooks integration for company {company_id}")
        else:
            # Create new
            import uuid
            company_integration = CompanyIntegration(
                id=str(uuid.uuid4()),
                company_id=company_id,
                integration_id=integration.id,
                status="pending",
                credentials={
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                config={"sandbox": sandbox},
            )
            session.add(company_integration)
            print(f"Created QuickBooks integration for company {company_id}")

        await session.commit()
        print("\n✅ QuickBooks credentials configured successfully!")
        print(f"\nNext steps:")
        print(f"1. Get the OAuth authorization URL:")
        print(f"   GET /api/integrations/quickbooks/{company_integration.id}/oauth/authorize")
        print(f"2. Complete the OAuth flow to authorize the connection")
        print(f"3. The integration will be activated automatically after OAuth")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Configure QuickBooks Online integration")
    parser.add_argument("--company-id", required=True, help="Company ID")
    parser.add_argument("--client-id", required=True, help="QuickBooks OAuth Client ID")
    parser.add_argument("--client-secret", required=True, help="QuickBooks OAuth Client Secret")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Use production environment (default: sandbox)",
    )

    args = parser.parse_args()

    asyncio.run(
        configure_quickbooks(
            company_id=args.company_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            sandbox=not args.production,
        )
    )

