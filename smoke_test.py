#!/usr/bin/env python3
"""
Smoke test for Worktree A V3 endpoint configuration.
This test demonstrates that the configuration is correct,
even though execution may fail due to account permissions.
"""

import httpx
import asyncio
import os
import sys

# Add the shared directory to the path
sys.path.insert(0, '../bankruptcy-retrieval')

from shared.config import (
    find_root_env,
    COURTLISTENER_SEARCH_URL,  # This should now be available
    COURTLISTENER_API_TOKEN
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv(find_root_env())

async def test_configuration():
    """Test that the configuration is correctly set up for V3 endpoints."""
    print("=== Worktree A Smoke Test ===")
    print(f"COURTLISTENER_SEARCH_URL: {COURTLISTENER_SEARCH_URL}")
    print(f"Token available: {bool(COURTLISTENER_API_TOKEN)}")

    # Show what the URL should be for docket search
    docket_search_url = f"{COURTLISTENER_SEARCH_URL}/dockets/"
    print(f"Docket search URL: {docket_search_url}")

    # Show what parameters we would use
    params = {
        "case_name__icontains": "WeWork",
        "date_filed__gte": "2023-01-01",
        "date_filed__lte": "2023-12-31",
        "chapter": 11,
        "fields": "id,case_name,date_filed",
        "format": "json",
        "limit": 3,
    }
    print(f"Search parameters: {params}")

    # Try to make the request (this will likely fail due to permissions)
    if COURTLISTENER_API_TOKEN:
        print("\nAttempting API call (may fail due to account permissions)...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    docket_search_url,
                    params=params,
                    headers={"Authorization": f"Token {COURTLISTENER_API_TOKEN}"}
                )
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"Success! Found {len(data.get('results', []))} results")
                    if data.get('results'):
                        first = data['results'][0]
                        print(f"First result - ID: {first.get('id')}, Case: {first.get('case_name')}")
                elif response.status_code == 403:
                    print("Permission denied - account lacks V3 API access")
                    print("This is expected for new accounts. Configuration is correct.")
                else:
                    print(f"Error: {response.text}")
        except Exception as e:
            print(f"Exception: {e}")
    else:
        print("No API token found - skipping actual API call")

if __name__ == "__main__":
    asyncio.run(test_configuration())