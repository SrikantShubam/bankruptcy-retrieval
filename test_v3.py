import httpx
import asyncio
import os
import sys

sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env
from dotenv import load_dotenv

load_dotenv(find_root_env())
token = os.environ.get('COURTLISTENER_API_TOKEN', 'NOT_FOUND')

async def test():
    print(f"Token loaded: {token[:15] if token != 'NOT_FOUND' else 'NOT_FOUND'}...")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://www.courtlistener.com/api/rest/v3/dockets/",
            params={
                "case_name__icontains": "WeWork",
                "date_filed__gte": "2023-01-01",
                "date_filed__lte": "2023-12-31",
                "chapter": 11,
                "fields": "id,case_name,date_filed",
                "format": "json",
                "limit": 3,
            },
            headers={"Authorization": f"Token {token}"}
        )
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Results count: {len(data.get('results', []))}")
            if data.get('results'):
                first_result = data['results'][0]
                print(f"First result - ID: {first_result.get('id')}, Case Name: {first_result.get('case_name')}")
            print(f"Response body: {r.text[:500]}")
        else:
            print(f"Error body: {r.text}")

if __name__ == "__main__":
    asyncio.run(test())