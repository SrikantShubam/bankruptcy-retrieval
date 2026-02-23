import asyncio
import httpx
import os
from dotenv import load_dotenv
load_dotenv('../bankruptcy-retrieval/.env')

async def test():
    token = os.environ.get('COURTLISTENER_API_TOKEN', '')
    headers = {'Authorization': f'Token {token}'}
    
    url = 'https://www.courtlistener.com/api/rest/v4/search/'
    
    # Try simpler query
    tests = [
        {'q': 'WeWork', 'type': 'r'},
        {'q': 'WeWork first day', 'type': 'r'},
        {'q': 'WeWork', 'type': 'd'},
    ]
    
    for params in tests:
        r = await httpx.AsyncClient().get(url, params=params, headers=headers)
        print(f'q={params["q"]}, type={params["type"]}: {r.status_code} -> {r.json().get("count", 0)} results')

asyncio.run(test())
