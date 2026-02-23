import httpx, asyncio, os
import sys

sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env
from dotenv import load_dotenv

load_dotenv(find_root_env())

async def test():
    token = os.environ.get('COURTLISTENER_API_TOKEN', 'NOT_FOUND')
    headers = {"Authorization": f"Token {token}"}
    base = "https://www.courtlistener.com/api/rest/v4/search/"
    tests = [
        {"q": '"WeWork" "first day declaration"', "type": "r", "available_only": "on", "filed_after": "2023-01-01", "filed_before": "2023-12-31"},
        {"q": 'WeWork short_description:"first day"', "type": "r", "available_only": "on", "filed_after": "2023-01-01", "filed_before": "2023-12-31"},
        {"q": '"WeWork" chapter:11', "type": "r", "order_by": "score desc"},
    ]
    async with httpx.AsyncClient(timeout=15) as client:
        for i, params in enumerate(tests, 1):
            r = await client.get(base, params=params, headers=headers)
            print(f"Test {i}: {r.status_code}")
            if r.status_code == 200:
                results = r.json().get("results", [])
                print(f"  count={r.json().get('count')}")
                for res in results[:2]:
                    print(f"  - {res.get('caseName')} | {res.get('short_description','')[:60]}")
                    print(f"    available: {res.get('is_available')} | filepath: {res.get('filepath_local','')[:50]}")
            else:
                print(f"  Error: {r.text[:200]}")

asyncio.run(test())