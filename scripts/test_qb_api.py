"""Test QuickBooks API connection by fetching company info."""
import asyncio
import sys
import json

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def test_api():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    # Add parent directory to path for imports
    sys.path.insert(0, 'C:/Users/rcarb/Downloads/FOPS/frontend/backend_v2')
    from app.services.quickbooks.quickbooks_client import QuickBooksAPIClient

    engine = create_async_engine(
        'postgresql+psycopg://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require'
    )

    # Get credentials from database
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT credentials, config FROM company_integration
                WHERE id = 'd7fbb80a-9ff0-41fd-92dc-dbe0eb9b826a'
            """)
        )
        row = result.fetchone()

        if not row:
            print("[ERROR] Integration not found!")
            return

        credentials = row[0] if isinstance(row[0], dict) else json.loads(row[0])

        print("=== QuickBooks Integration Credentials ===")
        print(f"  Client ID: {credentials.get('client_id', 'N/A')[:20]}...")
        print(f"  Realm ID: {credentials.get('realm_id', 'N/A')}")
        print(f"  Has Access Token: {'Yes' if credentials.get('access_token') else 'No'}")
        print(f"  Has Refresh Token: {'Yes' if credentials.get('refresh_token') else 'No'}")
        print(f"  Sandbox: {credentials.get('sandbox', True)}")

    # Create API client and test connection
    print("\n=== Testing QuickBooks API Connection ===")

    client = QuickBooksAPIClient(
        client_id=credentials['client_id'],
        client_secret=credentials['client_secret'],
        access_token=credentials.get('access_token'),
        refresh_token=credentials.get('refresh_token'),
        realm_id=credentials.get('realm_id'),
        sandbox=credentials.get('sandbox', True),
    )

    try:
        # Test by fetching company info
        response = await client.get_company_info()
        print("\n[OK] Successfully connected to QuickBooks!")

        # CompanyInfo response is nested
        company_info = response.get('CompanyInfo', response)
        print(f"  Company Name: {company_info.get('CompanyName', 'N/A')}")
        print(f"  Legal Name: {company_info.get('LegalName', 'N/A')}")
        print(f"  Country: {company_info.get('Country', 'N/A')}")
        print(f"  Fiscal Year Start: {company_info.get('FiscalYearStartMonth', 'N/A')}")

    except Exception as e:
        print(f"\n[ERROR] API call failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())
