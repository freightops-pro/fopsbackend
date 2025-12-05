"""
Script to test QuickBooks connection.

Usage:
    python -m app.scripts.test_quickbooks_connection --integration-id <integration_id>
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
from app.models.integration import CompanyIntegration, Integration
from app.services.quickbooks.quickbooks_service import QuickBooksService


async def test_connection(integration_id: str):
    """Test QuickBooks connection."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get the integration
        result = await session.execute(
            select(CompanyIntegration).where(CompanyIntegration.id == integration_id)
        )
        integration = result.scalar_one_or_none()

        if not integration:
            print(f"❌ ERROR: Integration {integration_id} not found")
            print("\nTo find your integration ID, run:")
            print("  SELECT id FROM company_integration WHERE integration_id = 'quickbooks-online';")
            return

        print(f"Testing QuickBooks connection for integration: {integration_id}")
        print(f"Company ID: {integration.company_id}")
        print(f"Status: {integration.status}")
        print()

        # Check if credentials are configured
        if not integration.credentials:
            print("❌ ERROR: No credentials configured")
            return

        client_id = integration.credentials.get("client_id")
        access_token = integration.credentials.get("access_token")
        realm_id = integration.config.get("realm_id") if integration.config else None

        print(f"Client ID: {client_id[:20]}..." if client_id else "❌ Not set")
        print(f"Access Token: {'✅ Set' if access_token else '❌ Not set'}")
        print(f"Realm ID: {realm_id if realm_id else '❌ Not set'}")
        print()

        if not access_token:
            print("❌ ERROR: Access token not found. Please complete OAuth flow first.")
            print("\nTo complete OAuth, use:")
            print("  POST /api/integrations/quickbooks/{integration_id}/oauth/complete")
            return

        if not realm_id:
            print("❌ ERROR: Realm ID not found. Please complete OAuth flow first.")
            return

        # Test connection
        print("Testing connection to QuickBooks...")
        try:
            service = QuickBooksService(session)
            result = await service.test_connection(integration)

            if result.get("success"):
                print("\n✅ Connection successful!")
                print(f"Company Name: {result.get('company_name', 'N/A')}")
                print(f"Message: {result.get('message')}")
            else:
                print("\n❌ Connection failed!")
                print(f"Error: {result.get('message')}")
        except Exception as e:
            print(f"\n❌ Connection test error: {str(e)}")
            import traceback
            traceback.print_exc()


async def list_integrations():
    """List all QuickBooks integrations."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            select(CompanyIntegration, Integration)
            .join(Integration)
            .where(Integration.integration_key == "quickbooks")
        )
        integrations = result.all()

        if not integrations:
            print("No QuickBooks integrations found.")
            print("\nTo create one, use:")
            print("  POST /api/integrations/company")
            print("  with integration_id: 'quickbooks-online'")
            return

        print("QuickBooks Integrations:")
        print("-" * 80)
        for company_int, int_catalog in integrations:
            print(f"Integration ID: {company_int.id}")
            print(f"  Company ID: {company_int.company_id}")
            print(f"  Status: {company_int.status}")
            print(f"  Realm ID: {company_int.config.get('realm_id') if company_int.config else 'Not set'}")
            print(f"  Has Access Token: {'Yes' if company_int.credentials and company_int.credentials.get('access_token') else 'No'}")
            print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test QuickBooks connection")
    parser.add_argument("--integration-id", help="CompanyIntegration ID to test")
    parser.add_argument("--list", action="store_true", help="List all QuickBooks integrations")

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_integrations())
    elif args.integration_id:
        asyncio.run(test_connection(args.integration_id))
    else:
        print("Please provide --integration-id or use --list to see available integrations")
        print("\nExample:")
        print("  python -m app.scripts.test_quickbooks_connection --list")
        print("  python -m app.scripts.test_quickbooks_connection --integration-id <id>")









