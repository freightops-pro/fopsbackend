import aiohttp
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

async def test():
    # Try the main Carrier dataset
    datasets = [
        ("u4i8-4m26", "Carrier - All With History"),
        ("6qg9-x4f8", "Carrier"),
        ("wahn-z3rq", "AuthHist - All With History"),
    ]

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-App-Token": os.getenv("FMCSA_APP_TOKEN", "")
    }

    for dataset_id, name in datasets:
        print(f"\n=== {name} ({dataset_id}) ===")
        url = f"https://data.transportation.gov/api/v3/views/{dataset_id}/query.json"
        query = "SELECT * LIMIT 1"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"query": query}, headers=headers) as resp:
                data = await resp.json()
                if isinstance(data, list) and data:
                    print("Columns with 'date' or 'auth':")
                    for k in sorted(data[0].keys()):
                        if 'date' in k.lower() or 'auth' in k.lower() or 'grant' in k.lower() or 'eff' in k.lower():
                            print(f"  ** {k}: {data[0][k]}")
                elif isinstance(data, dict) and data.get("error"):
                    print(f"Error: {data.get('message')}")
                else:
                    print(f"Response type: {type(data)}")

asyncio.run(test())
