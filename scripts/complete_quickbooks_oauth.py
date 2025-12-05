"""
Script to complete QuickBooks OAuth flow with an authorization code.

This script exchanges the authorization code for access and refresh tokens.

Usage:
    python -m app.scripts.complete_quickbooks_oauth \
        --integration-id <integration_id> \
        --authorization-code <code> \
        --realm-id <realm_id> \
        [--state <state>]
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.integration import CompanyIntegration


async def complete_oauth(
    integration_id: str,
    authorization_code: str,
    realm_id: str,
    state: str = None,
):
    """
    Complete QuickBooks OAuth flow by exchanging authorization code for tokens.

    Args:
        integration_id: CompanyIntegration ID
        authorization_code: OAuth authorization code from QuickBooks
        realm_id: QuickBooks company/realm ID
        state: OAuth state parameter (optional, for validation)
    """
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
            print(f"ERROR: Integration {integration_id} not found")
            return

        if not integration.credentials:
            print("ERROR: Integration credentials not configured")
            return

        client_id = integration.credentials.get("client_id")
        client_secret = integration.credentials.get("client_secret")

        if not client_id or not client_secret:
            print("ERROR: Client ID or Client Secret not found in credentials")
            return

        # Verify state if provided
        if state:
            stored_state = integration.config.get("oauth_state") if integration.config else None
            if stored_state != state:
                print("WARNING: State mismatch. Continuing anyway...")

        # Build redirect URI
        redirect_uri = f"{settings.get_api_base_url()}/integrations/quickbooks/{integration_id}/oauth/callback"

        print(f"Exchanging authorization code for tokens...")
        print(f"Client ID: {client_id[:20]}...")
        print(f"Redirect URI: {redirect_uri}")
        print(f"Realm ID: {realm_id}")

        # Exchange authorization code for tokens
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
                    data={
                        "grant_type": "authorization_code",
                        "code": authorization_code,
                        "redirect_uri": redirect_uri,
                    },
                    auth=(client_id, client_secret),
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                token_data = response.json()

                print("\n✅ Token exchange successful!")
                print(f"Access Token: {token_data.get('access_token', '')[:20]}...")
                print(f"Refresh Token: {token_data.get('refresh_token', '')[:20]}...")
                print(f"Expires In: {token_data.get('expires_in')} seconds")

                # Store tokens and realm_id
                if not integration.credentials:
                    integration.credentials = {}
                integration.credentials["access_token"] = token_data.get("access_token")
                integration.credentials["refresh_token"] = token_data.get("refresh_token")

                if not integration.config:
                    integration.config = {}
                integration.config["realm_id"] = realm_id
                integration.config["token_expires_at"] = (
                    token_data.get("expires_in") if token_data.get("expires_in") else None
                )

                # Clear OAuth state
                if integration.config.get("oauth_state"):
                    del integration.config["oauth_state"]

                integration.status = "active"
                from datetime import datetime
                integration.activated_at = datetime.utcnow()

                await session.commit()
                print("\n✅ QuickBooks integration activated successfully!")
                print(f"\nIntegration ID: {integration_id}")
                print(f"Realm ID: {realm_id}")
                print(f"Status: {integration.status}")
                print(f"\nYou can now use the integration to:")
                print(f"  - Sync customers: POST /api/integrations/quickbooks/{integration_id}/sync/customers")
                print(f"  - Sync invoices: POST /api/integrations/quickbooks/{integration_id}/sync/invoices")
                print(f"  - Test connection: POST /api/integrations/quickbooks/{integration_id}/test-connection")

        except httpx.HTTPStatusError as e:
            print(f"\n❌ Token exchange failed: {e.response.status_code}")
            print(f"Response: {e.response.text}")
            return
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            return


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Complete QuickBooks OAuth flow")
    parser.add_argument("--integration-id", required=True, help="CompanyIntegration ID")
    parser.add_argument("--authorization-code", required=True, help="OAuth authorization code")
    parser.add_argument("--realm-id", required=True, help="QuickBooks realm/company ID")
    parser.add_argument("--state", help="OAuth state parameter (optional)")

    args = parser.parse_args()

    asyncio.run(
        complete_oauth(
            integration_id=args.integration_id,
            authorization_code=args.authorization_code,
            realm_id=args.realm_id,
            state=args.state,
        )
    )









