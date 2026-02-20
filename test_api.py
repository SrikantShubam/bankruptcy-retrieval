import asyncio
import httpx
import os
import sys

sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env
from dotenv import load_dotenv

load_dotenv(find_root_env())
token = os.environ.get('COURTLISTENER_API_TOKEN', 'NOT_FOUND')

async def test():
    async with httpx.AsyncClient() as c:
        # Test RECAP search with type "r" - get first result
        r = await c.get(
            'https://www.courtlistener.com/api/rest/v4/search/',
            headers={'Authorization': f'Token {token}'},
            params={
                'q': 'WeWork first day declaration',
                'type': 'r',
                'filed_after': '2023-01-01',
                'filed_before': '2023-12-31',
                'order_by': 'score desc',
                'page_size': 1,
            },
            timeout=30.0
        )
        print(f'Status: {r.status_code}')
        data = r.json()
        results = data.get("results", [])
        if results:
            print(f"\nFirst result keys: {results[0].keys()}")
            print(f"\nFirst result: {results[0]}")
        else:
            print("No results")

asyncio.run(test())
