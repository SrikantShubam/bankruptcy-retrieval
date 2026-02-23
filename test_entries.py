import asyncio
import httpx
import os
from dotenv import load_dotenv
load_dotenv('../bankruptcy-retrieval/.env')

async def test():
    token = os.environ.get('COURTLISTENER_API_TOKEN', '')
    headers = {'Authorization': f'Token {token}'}
    
    # First get a docket ID
    r = await httpx.AsyncClient().get(
        'https://www.courtlistener.com/api/rest/v4/dockets/',
        params={'court': 'nysd', 'date_filed__gte': '2023-01-01', 'date_filed__lte': '2023-12-31', 'page_size': 1},
        headers=headers
    )
    if r.status_code != 200:
        print(f'Docket error: {r.status_code}')
        return
    
    docket_id = r.json()['results'][0]['id']
    print(f'Docket ID: {docket_id}')
    
    # Now test docket-entries with page_size
    r2 = await httpx.AsyncClient().get(
        f'https://www.courtlistener.com/api/rest/v4/docket-entries/',
        params={'docket': docket_id, 'page_size': 5},
        headers=headers
    )
    print(f'Entries status: {r2.status_code}')
    if r2.status_code == 200:
        print(f'Entries count: {r2.json().get("count", 0)}')
    else:
        print(f'Error: {r2.text[:200]}')

asyncio.run(test())
