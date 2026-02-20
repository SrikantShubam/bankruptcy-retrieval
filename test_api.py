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
        # Try without court filter - just search for WeWork
        r = await c.get(
            'https://www.courtlistener.com/api/rest/v4/search/',
            headers={'Authorization': f'Token {token}'},
            params={
                'q': 'WeWork',
            },
            timeout=30.0
        )
        print(f'Status: {r.status_code}')
        print(f'Body: {r.text[:2000]}')

asyncio.run(test())
