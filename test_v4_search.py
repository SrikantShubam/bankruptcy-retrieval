import asyncio
import httpx
import os
from dotenv import load_dotenv
load_dotenv('../bankruptcy-retrieval/.env')

async def test_v4_search():
    token = os.environ.get('COURTLISTENER_API_TOKEN', '')
    headers = {'Authorization': f'Token {token}'}
    
    url = 'https://www.courtlistener.com/api/rest/v4/search/'
    params = {
        'q': '"WeWork" short_description:"first day"',
        'type': 'r',
        'available_only': 'on',
        'order_by': 'score desc',
        'filed_after': '2023-01-01',
        'filed_before': '2023-12-31',
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, headers=headers)
        print(f'V4 search status: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            print(f'Results: {data.get("count", 0)}')
        else:
            print(f'Error: {r.text[:300]}')

asyncio.run(test_v4_search())
