import httpx
import asyncio
import os
from dotenv import load_dotenv
load_dotenv('.env')

async def test_simple_query():
    token = os.environ.get('COURTLISTENER_API_TOKEN')
    headers = {"Authorization": f"Token {token}"}

    # Try a simple query
    url = "https://www.courtlistener.com/api/rest/v4/search/"
    params = {
        "q": "WeWork",
        "type": "r",
        "available_only": "on",
    }

    print(f"Querying with params: {params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params, headers=headers)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Count: {data.get('count')}")
            results = data.get('results', [])
            print(f"Results: {len(results)}")

            for i, result in enumerate(results[:3]):
                print(f"Result {i+1}:")
                print(f"  Short description: {result.get('short_description', '')}")
                print(f"  Case name: {result.get('caseName', '')}")
                print(f"  Date filed: {result.get('dateFiled', '')}")
                print(f"  Filepath: {result.get('filepath_local', '')}")
                print(f"  Available: {result.get('is_available', False)}")

asyncio.run(test_simple_query())