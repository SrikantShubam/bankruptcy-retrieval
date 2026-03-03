import asyncio
import os
import httpx
from dotenv import load_dotenv
load_dotenv('.env')

async def test_broad_search():
    token = os.environ.get('COURTLISTENER_API_TOKEN')
    if not token:
        print("COURTLISTENER_API_TOKEN not set")
        return

    headers = {"Authorization": f"Token {token}"}

    # Try a broad search for WeWork bankruptcy documents
    url = "https://www.courtlistener.com/api/rest/v4/search/"
    params = {
        "q": '"WeWork" chapter:11',
        "type": "r",
        "available_only": "on",
        "order_by": "score desc",
        "filed_after": "2023-01-01",
        "filed_before": "2023-12-31",
    }

    print(f"Querying with params: {params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Total results: {data.get('count', 0)}")
                results = data.get("results", [])
                print(f"First {min(5, len(results))} results:")
                for i, result in enumerate(results[:5]):
                    print(f"  {i+1}. {result.get('short_description', '')}")
                    print(f"     Date: {result.get('dateFiled', '')}")
                    print(f"     Available: {result.get('is_available', False)}")
                    print(f"     Filepath: {result.get('filepath_local', '')}")
            else:
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_broad_search())