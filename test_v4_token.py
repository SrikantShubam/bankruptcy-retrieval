import asyncio
import httpx
import os
import sys
sys.path.insert(0, '..')
from dotenv import load_dotenv

# Load from correct path
load_dotenv('../bankruptcy-retrieval/.env')
token = os.environ.get('COURTLISTENER_API_TOKEN', '')
print(f'Token loaded: {bool(token)}')

async def test_v4():
    headers = {'Authorization': f'Token {token}'}
    # Test V4 dockets endpoint
    url = 'https://www.courtlistener.com/api/rest/v4/dockets/'
    params = {
        'date_filed__gte': '2023-01-01',
        'date_filed__lte': '2023-12-31',
        'case_name__icontains': 'WeWork',
        'limit': 3,
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, headers=headers)
        print(f'V4 dockets status: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            print(f'Results: {data.get("count", 0)}')
            if data.get('results'):
                print(f'First: {data["results"][0].get("case_name")}')
        else:
            print(f'Error: {r.text[:300]}')

asyncio.run(test_v4())
