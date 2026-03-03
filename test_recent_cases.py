import asyncio
import os
import httpx
from dotenv import load_dotenv
load_dotenv('.env')

async def test_recent_cases():
    token = os.environ.get('COURTLISTENER_API_TOKEN')
    if not token:
        print("COURTLISTENER_API_TOKEN not set")
        return

    headers = {"Authorization": f"Token {token}"}

    # Try a search for recent bankruptcy filings with available documents
    url = "https://www.courtlistener.com/api/rest/v4/search/"
    params = {
        "q": "chapter:11",
        "type": "r",
        "available_only": "on",
        "order_by": "dateFiled desc",
        "limit": 10,
    }

    print(f"Querying recent available bankruptcy documents...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Total results: {data.get('count', 0)}")
                results = data.get("results", [])
                print(f"First {min(10, len(results))} results:")
                for i, result in enumerate(results[:10]):
                    title = result.get('short_description', '') or result.get('caseName', '')
                    print(f"  {i+1}. {title}")
                    print(f"     Date: {result.get('dateFiled', '')}")
                    print(f"     Available: {result.get('is_available', False)}")
                    print(f"     Filepath: {result.get('filepath_local', '')}")
                    print()
            else:
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_recent_cases())