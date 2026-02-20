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
        # Test RECAP search with type "r"
        r = await c.get(
            'https://www.courtlistener.com/api/rest/v4/search/',
            headers={'Authorization': f'Token {token}'},
            params={
                'q': 'WeWork first day declaration',
                'type': 'r',  # RECAP documents
                'filed_after': '2023-01-01',
                'filed_before': '2023-12-31',
                'order_by': 'score desc',
                'page_size': 5,
            },
            timeout=30.0
        )
        print(f'Status: {r.status_code}')
        print(f'Body: {r.text[:2000]}')

asyncio.run(test())
