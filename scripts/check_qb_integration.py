"""Check QuickBooks integration in database."""
import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def check():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        'postgresql+psycopg://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require'
    )

    async with engine.connect() as conn:
        # Check for QuickBooks integration in catalog
        result = await conn.execute(
            text("SELECT id, integration_key, display_name FROM integration WHERE integration_key = 'quickbooks'")
        )
        row = result.fetchone()
        if row:
            print(f"QuickBooks Integration Found: id={row[0]}, key={row[1]}, name={row[2]}")
        else:
            print("No QuickBooks integration found in catalog")

        # Check for any company integrations with QuickBooks
        result2 = await conn.execute(
            text("""
                SELECT ci.id, ci.company_id, ci.status, ci.credentials IS NOT NULL as has_creds
                FROM company_integration ci
                JOIN integration i ON i.id = ci.integration_id
                WHERE i.integration_key = 'quickbooks'
            """)
        )
        rows = result2.fetchall()
        if rows:
            for r in rows:
                print(f"Company Integration: id={r[0]}, company={r[1]}, status={r[2]}, has_credentials={r[3]}")
        else:
            print("No company QuickBooks integrations found - need to create one first")

        # List available companies
        result3 = await conn.execute(
            text("SELECT id, name FROM company LIMIT 5")
        )
        companies = result3.fetchall()
        print(f"\nAvailable companies: {[(c[0], c[1]) for c in companies]}")

if __name__ == "__main__":
    asyncio.run(check())
