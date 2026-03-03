import asyncio, httpx, os, json
from dotenv import load_dotenv
load_dotenv('.env')

async def debug():
    token = os.environ.get('COURTLISTENER_API_TOKEN')
    headers = {"Authorization": f"Token {token}"}
    SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"

    params = {
        "q": '"WeWork" short_description:"first day"',
        "type": "r",
        "available_only": "on",
        "order_by": "score desc",
        "filed_after": "2023-01-01",
        "filed_before": "2023-12-31"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(SEARCH_URL, params=params, headers=headers)
        print(f"Status: {r.status_code}")
        data = r.json()
        print(f"Count: {data.get('count')}")
        results = data.get('results', [])
        print(f"Results returned: {len(results)}")
        for i, res in enumerate(results[:3]):
            print(f"\n--- Result {i} ---")
            print(json.dumps(res, indent=2, default=str))

asyncio.run(debug())