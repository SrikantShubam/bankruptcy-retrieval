import httpx
import asyncio
import os
import sys

sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env
from dotenv import load_dotenv

load_dotenv(find_root_env())
token = os.environ.get('COURTLISTENER_API_TOKEN', 'NOT_FOUND')

async def test_v4():
    print(f"Testing V4 API with token: {token[:15] if token != 'NOT_FOUND' else 'NOT_FOUND'}...")
    async with httpx.AsyncClient() as client:
        # Test V4 endpoint with filter-based query (should work)
        r = await client.get(
            "https://www.courtlistener.com/api/rest/v4/dockets/",
            params={
                "fields": "id,case_name,date_filed",
                "format": "json",
                "limit": 3,
            },
            headers={"Authorization": f"Token {token}"}
        )
        print(f"V4 Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"V4 Results count: {len(data.get('results', []))}")
            print(f"V4 Response body: {r.text[:500]}")
        else:
            print(f"V4 Error body: {r.text}")

async def test_v3():
    print(f"Testing V3 API with token: {token[:15] if token != 'NOT_FOUND' else 'NOT_FOUND'}...")
    async with httpx.AsyncClient() as client:
        # Test V3 endpoint with search-based query (might have permissions issue)
        r = await client.get(
            "https://www.courtlistener.com/api/rest/v3/dockets/",
            params={
                "fields": "id,case_name,date_filed",
                "format": "json",
                "limit": 3,
            },
            headers={"Authorization": f"Token {token}"}
        )
        print(f"V3 Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"V3 Results count: {len(data.get('results', []))}")
            print(f"V3 Response body: {r.text[:500]}")
        else:
            print(f"V3 Error body: {r.text}")

async def main():
    await test_v4()
    print()
    await test_v3()

if __name__ == "__main__":
    asyncio.run(main())