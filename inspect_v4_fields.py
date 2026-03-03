import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def inspect_v4_fields():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Search for a recent bankruptcy filing to see what fields are available
    params = {
        "q": '"Yellow Corporation" chapter:11',
        "type": "r",
        "order_by": "dateFiled desc",
        "page_size": 3
    }

    print(f"Inspecting V4 search response fields with params: {params}")

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
                results = data.get("results", [])

                print(f"Found {len(results)} results")

                for i, result in enumerate(results):
                    print(f"\n--- Result {i+1} ---")
                    print(f"Keys available: {list(result.keys())}")

                    # Print all fields to see what's available
                    for key, value in result.items():
                        # Only print non-null values or first 100 chars of long strings
                        if value is not None:
                            if isinstance(value, str) and len(value) > 100:
                                print(f"{key}: {value[:100]}...")
                            else:
                                print(f"{key}: {value}")
                        else:
                            print(f"{key}: {value}")

                    # Break after first result to avoid too much output
                    break

            else:
                print(f"Request failed: {response.status_code}")
                print(response.text[:500])

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(inspect_v4_fields())