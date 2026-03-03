import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def debug_search_any_documents():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Try a simple search for recent bankruptcy filings without availability filter
    params = {
        "q": '"Yellow Corporation" chapter:11',
        "type": "r",
        "order_by": "dateFiled desc",
        "page_size": 10
    }

    print(f"Searching with params: {params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=params,
                headers=headers
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Total results: {data.get('count', 0)}")
                results = data.get("results", [])
                print(f"Returned results: {len(results)}")

                for i, result in enumerate(results):
                    print(f"\n--- Result {i+1} ---")
                    print(f"ID: {result.get('id')}")
                    print(f"Case Name: {result.get('caseName')}")
                    print(f"Short Description: {result.get('short_description')}")
                    print(f"Date Filed: {result.get('dateFiled')}")
                    print(f"Is Available: {result.get('is_available')}")
                    print(f"Filepath Local: {result.get('filepath_local')}")
                    print(f"Download URL: {result.get('download_url')}")
                    print(f"Absolute URL: {result.get('absolute_url')}")

                    # Check if any of the fields that indicate availability are present
                    has_content = any([
                        result.get('filepath_local'),
                        result.get('download_url'),
                        result.get('absolute_url')
                    ])
                    print(f"Has content indicators: {has_content}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_search_any_documents())