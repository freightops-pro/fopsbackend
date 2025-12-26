import aiohttp
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

async def test():
    url = "https://data.transportation.gov/api/v3/views/6eyk-hxee/query.json"
    query = "SELECT * WHERE `bus_state_code` = 'TX' AND (`common_stat` = 'A' OR `contract_stat` = 'A') LIMIT 1"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-App-Token": os.getenv("FMCSA_APP_TOKEN", "")
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"query": query}, headers=headers) as resp:
            data = await resp.json()
            if "rows" in data and data["rows"]:
                print("All columns:")
                for k in sorted(data["rows"][0].keys()):
                    print(f"  {k}: {data['rows'][0][k]}")
            else:
                print(f"Response: {data}")

asyncio.run(test())
