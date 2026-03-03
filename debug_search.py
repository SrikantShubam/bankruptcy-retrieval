import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def debug_search():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Test search for Yellow Corporation with minimal filters
    params = {
        "q": '"Yellow Corporation" short_description:"first day"',
        "type": "r",
        "order_by": "score desc",
        "filed_after": "2023-01-01",
        "filed_before": "2023-12-31",
        "court": "deb"
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

                for i, result in enumerate(results[:3]):  # Show first 3 results
                    print(f"\n--- Result {i+1} ---")
                    print(f"ID: {result.get('id')}")
                    print(f"Case Name: {result.get('caseName')}")
                    print(f"Short Description: {result.get('short_description')}")
                    print(f"Date Filed: {result.get('dateFiled')}")
                    print(f"Is Available: {result.get('is_available')}")
                    print(f"Filepath Local: {result.get('filepath_local')}")
                    print(f"Download URL: {result.get('download_url')}")
                    print(f"Absolute URL: {result.get('absolute_url')}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_search())