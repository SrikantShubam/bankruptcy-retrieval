import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def check_api_endpoints():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Check the root API endpoint to see what's available
    endpoints_to_check = [
        "https://www.courtlistener.com/api/rest/v4/",
        "https://www.courtlistener.com/api/rest/v3/",
    ]

    for endpoint in endpoints_to_check:
        print(f"\n=== Checking {endpoint} ===")
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(endpoint, headers=headers)
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    print("Response:", response.json())
                else:
                    print("Response text:", response.text[:500])
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_api_endpoints())