import asyncio
import httpx
import os
import sys
sys.path.insert(0, '..')
from dotenv import load_dotenv

load_dotenv('../bankruptcy-retrieval/.env')
token = os.environ.get('COURTLISTENER_API_TOKEN', '')

async def test_v4_valid():
    headers = {'Authorization': f'Token {token}'}
    url = 'https://www.courtlistener.com/api/rest/v4/dockets/'
    # Use court and date range only (valid V4 params)
    params = {
        'date_filed__gte': '2023-01-01',
        'date_filed__lte': '2023-12-31',
        'court': 'nysd',  # S.D.N.Y.
        'page_size': 3,
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, headers=headers)
        print(f'Status: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            print(f'Count: {data.get("count", 0)}')
            if data.get('results'):
                for d in data['results'][:3]:
                    print(f'  - {d.get("case_name")}')
        else:
            print(f'Error: {r.text[:200]}')

asyncio.run(test_v4_valid())
