#!/usr/bin/env python3
"""Test the updated scout.py with V4 search endpoint"""

import asyncio
import httpx
import sys

sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import (
    find_root_env,
    COURTLISTENER_API_TOKEN,
    COURTLISTENER_V4_SEARCH_URL,
    get_court_slug,
    PRIORITY_KEYWORDS
)
from dotenv import load_dotenv

load_dotenv(find_root_env())

async def test_find_docket():
    """Test finding a docket for WeWork"""
    print("=== Testing find_docket (V4 search endpoint) ===")

    token = COURTLISTENER_API_TOKEN
    if not token:
        print("No API token found")
        return

    headers = {"Authorization": f"Token {token}"}

    company_name = "WeWork"
    filing_year = 2023
    court = "S.D.N.Y."

    # Build the query as scout.py would
    court_slug = get_court_slug(court)

    params = {
        "q": f'"{company_name}" chapter:11',
        "type": "r",
        "available_only": "on",
        "order_by": "score desc",
        "filed_after": f"{filing_year}-01-01",
        "filed_before": f"{filing_year}-12-31",
    }

    if court_slug:
        params["court"] = court_slug

    print(f"Search URL: {COURTLISTENER_V4_SEARCH_URL}")
    print(f"Search params: {params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(COURTLISTENER_V4_SEARCH_URL, params=params, headers=headers)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                count = data.get('count', 0)
                results = data.get('results', [])

                print(f"Found {count} results")
                if results:
                    first_result = results[0]
                    print(f"First result:")
                    print(f"  Case Name: {first_result.get('caseName')}")
                    print(f"  Docket ID: {first_result.get('id')}")
                    print(f"  Court: {first_result.get('court')}")
                    print(f"  Filed: {first_result.get('dateFiled')}")
                    print(f"  Docket Number: {first_result.get('docketNumber')}")

                    # Return the first result for further testing
                    return first_result.get('id')
                else:
                    print("No results found")
            else:
                print(f"Error: {response.text[:300]}")

        except Exception as e:
            print(f"Exception: {e}")

    return None

async def test_find_docket_entries(docket_id):
    """Test finding docket entries for a given docket ID"""
    if not docket_id:
        print("No docket ID provided, skipping docket entries test")
        return

    print(f"\n=== Testing find_docket_entries for docket {docket_id} ===")

    token = COURTLISTENER_API_TOKEN
    headers = {"Authorization": f"Token {token}"}

    # Test with first keyword
    keyword = PRIORITY_KEYWORDS[0] if PRIORITY_KEYWORDS else "first day declaration"

    params = {
        "q": f'docket_id:{docket_id} "{keyword}"',
        "type": "r",
        "available_only": "on",
        "order_by": "score desc",
        "filed_after": "2019-01-01",
    }

    print(f"Search URL: {COURTLISTENER_V4_SEARCH_URL}")
    print(f"Search params: {params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(COURTLISTENER_V4_SEARCH_URL, params=params, headers=headers)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                count = data.get('count', 0)
                results = data.get('results', [])

                print(f"Found {count} entries matching '{keyword}'")
                if results:
                    first_entry = results[0]
                    print(f"First entry:")
                    print(f"  Description: {first_entry.get('short_description')}")
                    print(f"  Entry ID: {first_entry.get('id')}")
                    print(f"  Filed: {first_entry.get('dateFiled')}")
                    print(f"  Available: {first_entry.get('is_available')}")
                else:
                    print(f"No entries found for keyword '{keyword}'")
            else:
                print(f"Error: {response.text[:300]}")

        except Exception as e:
            print(f"Exception: {e}")

async def main():
    print("Testing Worktree A Scout with V4 Search Endpoint")
    print("=" * 50)

    # Test docket search
    docket_id = await test_find_docket()

    # Test docket entries search if we found a docket
    if docket_id:
        await test_find_docket_entries(docket_id)

    print("\n" + "=" * 50)
    print("Test complete")

if __name__ == "__main__":
    asyncio.run(main())