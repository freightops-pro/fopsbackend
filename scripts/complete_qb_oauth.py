"""Complete QuickBooks OAuth by exchanging authorization code for tokens."""
import asyncio
import sys
import json

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Credentials
CLIENT_ID = "ABBebmkRwW2gUN6eiW4z1UIJz8OszSXflqksfQh5J2enkUZyDw"
CLIENT_SECRET = "OsUoX77TKVMCZCTK6eyCzbpabdUm2oAizwzkh0cR"
PLAYGROUND_REDIRECT = "https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl"

async def complete_oauth(auth_code: str, realm_id: str, integration_id: str):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from intuitlib.client import AuthClient

    print(f"\nExchanging authorization code for tokens...")
    print(f"  Auth Code: {auth_code[:20]}...")
    print(f"  Realm ID: {realm_id}")
    print(f"  Integration ID: {integration_id}")

    # Exchange code for tokens using SDK
    auth_client = AuthClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=PLAYGROUND_REDIRECT,
        environment="sandbox",
    )

    try:
        auth_client.get_bearer_token(auth_code, realm_id=realm_id)

        access_token = auth_client.access_token
        refresh_token = auth_client.refresh_token
        expires_in = auth_client.expires_in

        print(f"\n[OK] Token exchange successful!")
        print(f"  Access Token: {access_token[:30]}...")
        print(f"  Refresh Token: {refresh_token[:30]}...")
        print(f"  Expires In: {expires_in} seconds")

    except Exception as e:
        print(f"\n[ERROR] Token exchange failed: {e}")
        return

    # Update database with tokens
    engine = create_async_engine(
        'postgresql+psycopg://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require'
    )

    async with engine.begin() as conn:
        # Get existing credentials
        result = await conn.execute(
            text("SELECT credentials FROM company_integration WHERE id = :id"),
            {"id": integration_id}
        )
        row = result.fetchone()

        if not row:
            print(f"\n[ERROR] Integration {integration_id} not found!")
            return

        # Handle both string JSON and dict (from JSONB column)
        if row[0] is None:
            credentials = {}
        elif isinstance(row[0], dict):
            credentials = row[0]
        else:
            credentials = json.loads(row[0])

        # Update credentials with tokens
        credentials.update({
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "realm_id": realm_id,
            "sandbox": True,
        })

        # Update integration record
        await conn.execute(
            text("""
                UPDATE company_integration
                SET
                    credentials = :credentials,
                    status = 'active',
                    config = jsonb_set(COALESCE(config, '{}')::jsonb, '{realm_id}', :realm_id_json),
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": integration_id,
                "credentials": json.dumps(credentials),
                "realm_id_json": json.dumps(realm_id),
            }
        )

        print(f"\n[OK] Database updated successfully!")
        print(f"  Integration status: active")
        print(f"\nQuickBooks integration is now ready to use!")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python complete_qb_oauth.py <auth_code> <realm_id> <integration_id>")
        print("\nExample:")
        print("  python scripts/complete_qb_oauth.py AB11234567890 1234567890 d7fbb80a-9ff0-41fd-92dc-dbe0eb9b826a")
        sys.exit(1)

    auth_code = sys.argv[1]
    realm_id = sys.argv[2]
    integration_id = sys.argv[3]

    asyncio.run(complete_oauth(auth_code, realm_id, integration_id))
