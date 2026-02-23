# smoke_test_v4_search.py
import httpx, asyncio, os
import sys

sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env
from dotenv import load_dotenv

load_dotenv(find_root_env())

async def test():
    token = os.environ.get('COURTLISTENER_API_TOKEN', 'NOT_FOUND')
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://www.courtlistener.com/api/rest/v4/search/",
            params={
                "q": 'WeWork "first day declaration"',
                "type": "r",
                "available_only": "on",
                "order_by": "score desc",
                "filed_after": "2023-01-01",
                "filed_before": "2023-12-31",
            },
            headers={"Authorization": f"Token {token}"}
        )
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Count: {data.get('count')}")
            for result in data.get('results', [])[:3]:
                print(f"  - {result.get('caseName')} | {result.get('short_description')} | available: {result.get('is_available')}")
        else:
            print(r.text[:300])

asyncio.run(test())