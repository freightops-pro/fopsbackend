import aiohttp
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

FMCSA_APP_TOKEN = os.getenv("FMCSA_APP_TOKEN", "")

async def test():
    url = "https://data.transportation.gov/api/v3/views/az4n-8mr2/query.json"

    # Calculate cutoff for last 30 days
    cutoff_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y%m%d")

    # Test query with date filter
    # power_units filtering will be done client-side since SoQL doesn't support CAST
    query = f"""SELECT *
WHERE `phy_state` = 'TX'
AND `status_code` = 'A'
AND `add_date` >= '{cutoff_date}'
ORDER BY `add_date` DESC
LIMIT 50"""

    print(f"Query: {query}")
    print(f"Cutoff date: {cutoff_date}")
    print()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-App-Token": FMCSA_APP_TOKEN
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"query": query}, headers=headers) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()

            if isinstance(data, list) and data:
                print(f"Found {len(data)} carriers")
                for c in data:
                    print(f"\n  Company: {c.get('legal_name')}")
                    print(f"  DOT: {c.get('dot_number')}")
                    print(f"  State: {c.get('phy_state')}")
                    print(f"  Trucks: {c.get('power_units')}")
                    print(f"  Add Date: {c.get('add_date')}")
                    print(f"  Phone: {c.get('phone')}")
                    print(f"  Email: {c.get('email_address')}")
            elif isinstance(data, list) and not data:
                print("No carriers found matching criteria")
            elif isinstance(data, dict) and data.get("error"):
                print(f"Error: {data.get('message')}")
            else:
                print(f"Response: {data}")

asyncio.run(test())
