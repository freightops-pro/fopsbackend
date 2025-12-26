import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

FMCSA_APP_TOKEN = os.getenv("FMCSA_APP_TOKEN", "")
FMCSA_SECRET_TOKEN = os.getenv("FMCSA_SECRET_TOKEN", "")

async def test_query():
    url = "https://data.transportation.gov/api/v3/views/6eyk-hxee/query.json"
    
    # Simple query to get column names
    query = "SELECT * WHERE `bus_state_code` = 'TX' LIMIT 1"
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if FMCSA_APP_TOKEN:
        headers["X-App-Token"] = FMCSA_APP_TOKEN
    if FMCSA_SECRET_TOKEN:
        headers["X-App-Secret"] = FMCSA_SECRET_TOKEN
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"query": query}, headers=headers) as resp:
            data = await resp.json()
            
            if isinstance(data, dict) and "rows" in data:
                rows = data["rows"]
                if rows:
                    print("Available columns:")
                    for key in sorted(rows[0].keys()):
                        val = rows[0][key]
                        # Look for date-related columns
                        if 'date' in key.lower() or 'auth' in key.lower() or 'add' in key.lower():
                            print(f"  ** {key}: {val}")
                        else:
                            print(f"     {key}: {val}")

asyncio.run(test_query())
