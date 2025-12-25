import requests
import json

# v3 API endpoint
url = 'https://data.transportation.gov/api/v3/views/6eyk-hxee/query.json'

# SoQL query
query_payload = {
    "query": "SELECT * WHERE `bus_state_code` = 'TX' AND (`common_stat` = 'A' OR `contract_stat` = 'A') ORDER BY `legal_name` ASC LIMIT 5"
}

headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-App-Token': 'bmFz2B4ICFPtBUGD0xsjipGLc',
    'X-App-Secret': 'GfTtdB8j4DWI0fJ-qb6hd-OWwf2mxYd_6cw_'
}

print('Testing FMCSA v3 API with SoQL...')
print(f'Query: {query_payload["query"]}')
print()

try:
    response = requests.post(url, json=query_payload, headers=headers, timeout=30)
    print(f'Status: {response.status_code}')

    if response.status_code == 200:
        data = response.json()

        # Handle v3 response structure
        if isinstance(data, list):
            carriers = data
        else:
            carriers = data.get('rows', data.get('data', []))
            print(f'Response keys: {data.keys() if isinstance(data, dict) else "N/A"}')

        print(f'Records returned: {len(carriers)}')
        print()

        for i, carrier in enumerate(carriers[:5]):
            name = carrier.get('legal_name') or carrier.get('dba_name') or 'Unknown'
            dot = carrier.get('dot_number', 'N/A')
            phone = carrier.get('bus_telno', 'N/A')
            state = carrier.get('bus_state_code', 'N/A')
            print(f'{i+1}. {name[:50]} | DOT: {dot} | State: {state} | Phone: {phone}')
    else:
        print(f'Error Response: {response.text[:1000]}')
except Exception as e:
    print(f'Exception: {e}')
