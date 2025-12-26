import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

FMCSA_APP_TOKEN = os.getenv("FMCSA_APP_TOKEN", "")
FMCSA_SECRET_TOKEN = os.getenv("FMCSA_SECRET_TOKEN", "")

async def test_query():
    url = "https://data.transportation.gov/api/v3/views/6eyk-hxee/query.json"
    
    # Test with authority_days = 30
    from datetime import datetime, timedelta
    cutoff_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
    
    query = f"SELECT * WHERE `bus_state_code` = 'TX' AND (`common_stat` = 'A' OR `contract_stat` = 'A') AND `add_date` >= '{cutoff_date}' ORDER BY `legal_name` ASC LIMIT 10"
    
    print(f"Query: {query}")
    print()
    
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
            print(f"Status: {resp.status}")
            data = await resp.json()
            
            if isinstance(data, dict):
                print(f"Response keys: {data.keys()}")
                if "error" in data:
                    print(f"Error: {data}")
                elif "rows" in data:
                    rows = data["rows"]
                    print(f"Rows: {len(rows)}")
                    for r in rows[:3]:
                        print(f"  - {r.get('legal_name')} | DOT: {r.get('dot_number')} | Added: {r.get('add_date')}")
                else:
                    print(f"Full response: {data}")
            else:
                print(f"Response is list with {len(data)} items")
                for r in data[:3]:
                    print(f"  - {r.get('legal_name')} | DOT: {r.get('dot_number')}")

asyncio.run(test_query())
