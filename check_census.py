import aiohttp
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

async def test():
    # Check Company Census File dataset
    datasets = [
        ("az4n-8mr2", "Company Census File"),
        ("4a2k-zf79", "Motor Carrier Registrations - Census Files"),
        ("kjg3-diqy", "SMS Input - Motor Carrier Census Information"),
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
            try:
                async with session.post(url, json={"query": query}, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()
                    if isinstance(data, list) and data:
                        print("Date-related columns:")
                        for k in sorted(data[0].keys()):
                            if 'date' in k.lower() or 'add' in k.lower() or 'eff' in k.lower() or 'grant' in k.lower():
                                print(f"  ** {k}: {data[0][k]}")
                        print("\nAll columns:")
                        for k in sorted(data[0].keys()):
                            print(f"  {k}")
                    elif isinstance(data, dict) and data.get("error"):
                        print(f"Error: {data.get('message')}")
                    else:
                        print(f"Response: {data}")
            except Exception as e:
                print(f"Exception: {e}")

asyncio.run(test())
