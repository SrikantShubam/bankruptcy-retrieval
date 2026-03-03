import asyncio, httpx, os, json
from dotenv import load_dotenv
load_dotenv('.env')

async def debug():
    token = os.environ.get('COURTLISTENER_API_TOKEN')
    print(f"Token loaded: {token[:10] if token else 'None'}")
    headers = {"Authorization": f"Token {token}"}

    SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"

    queries = [
        '"WeWork" short_description:"first day"',
        '"WeWork" short_description:"declaration"',
        '"WeWork" chapter:11',
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for q in queries:
            params = {
                "q": q, "type": "r", "available_only": "on",
                "order_by": "score desc",
                "filed_after": "2023-01-01", "filed_before": "2023-12-31"
            }
            r = await client.get(SEARCH_URL, params=params, headers=headers)
            print(f"\n=== Query: {q} ===")
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print(f"Total count: {data.get('count')}")
                results = data.get('results', [])[:3]
                print(f"Number of results: {len(results)}")
                for i, res in enumerate(results):
                    print(f"  Result {i+1}:")
                    print(f"    All keys: {list(res.keys())}")
                    # Print all fields
                    for key, value in res.items():
                        if key in ['id', 'caseName', 'short_description', 'filepath_local', 'is_available', 'dateFiled', 'recap_documents']:
                            print(f"    {key}={value}")
                    print("  ---")
            else:
                print(f"Error: {r.text[:200]}")

asyncio.run(debug())