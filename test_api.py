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
    print(f"Token loaded: {token[:15] if token != 'NOT_FOUND' else 'NOT_FOUND'}...")
    async with httpx.AsyncClient() as c:
        try:
            r = await c.get(
                'https://www.courtlistener.com/api/rest/v4/dockets/',
                headers={'Authorization': f'Token {token}'},
                params={'case_name__icontains': 'WeWork', 'chapter': 11},
                timeout=30.0
            )
            print(f'Status: {r.status_code}')
            print(f'Body: {r.text[:500]}')
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())