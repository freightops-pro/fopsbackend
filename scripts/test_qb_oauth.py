"""Test QuickBooks OAuth flow with provided credentials."""
import asyncio
import sys
import json
import uuid

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Credentials
CLIENT_ID = "ABBebmkRwW2gUN6eiW4z1UIJz8OszSXflqksfQh5J2enkUZyDw"
CLIENT_SECRET = "OsUoX77TKVMCZCTK6eyCzbpabdUm2oAizwzkh0cR"
COMPANY_ID = "42c238f6-4721-4000-a3f0-ee3cf73f3a2b"  # Test Freight Company

async def setup_and_test():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from intuitlib.client import AuthClient
    from intuitlib.enums import Scopes

    engine = create_async_engine(
        'postgresql+psycopg://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require'
    )

    async with engine.begin() as conn:
        # Check if company integration already exists
        result = await conn.execute(
            text("""
                SELECT ci.id FROM company_integration ci
                JOIN integration i ON i.id = ci.integration_id
                WHERE ci.company_id = :company_id AND i.integration_key = 'quickbooks'
            """),
            {"company_id": COMPANY_ID}
        )
        existing = result.fetchone()

        if existing:
            integration_id = existing[0]
            print(f"Found existing company integration: {integration_id}")
            # Update credentials
            await conn.execute(
                text("""
                    UPDATE company_integration
                    SET credentials = :credentials, updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "id": integration_id,
                    "credentials": json.dumps({
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET
                    })
                }
            )
            print("Updated credentials")
        else:
            # Create new company integration
            integration_id = str(uuid.uuid4())
            await conn.execute(
                text("""
                    INSERT INTO company_integration (
                        id, company_id, integration_id, status, credentials, config, auto_sync, created_at, updated_at
                    ) VALUES (
                        :id, :company_id, 'quickbooks-online', 'pending', :credentials, '{}', false, NOW(), NOW()
                    )
                """),
                {
                    "id": integration_id,
                    "company_id": COMPANY_ID,
                    "credentials": json.dumps({
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET
                    })
                }
            )
            print(f"Created company integration: {integration_id}")

    # Test generating OAuth URL using the SDK
    print("\n--- Testing OAuth URL Generation ---")
    redirect_uri = f"http://localhost:8000/api/integrations/quickbooks/{integration_id}/oauth/callback"

    auth_client = AuthClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=redirect_uri,
        environment="sandbox",
    )

    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])

    print(f"\nCompany Integration ID: {integration_id}")
    print(f"\nRedirect URI: {redirect_uri}")
    print(f"\nState Token: {auth_client.state_token}")
    print(f"\n*** OAuth Authorization URL ***")
    print(f"\n{auth_url}")
    print("\n\nOpen this URL in your browser to authorize QuickBooks!")

if __name__ == "__main__":
    asyncio.run(setup_and_test())
