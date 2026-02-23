import httpx
import asyncio
import os
import sys

sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env
from dotenv import load_dotenv

load_dotenv(find_root_env())
token = os.environ.get('COURTLISTENER_API_TOKEN', 'NOT_FOUND')

async def test_v4_fields():
    print(f"Testing V4 API fields...")
    async with httpx.AsyncClient() as client:
        # Test what fields are supported by V4
        r = await client.get(
            "https://www.courtlistener.com/api/rest/v4/dockets/",
            params={
                "fields": "id,case_name,date_filed,court,docket_number",
                "format": "json",
                "limit": 3,
            },
            headers={"Authorization": f"Token {token}"}
        )
        print(f"V4 Fields Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"V4 Fields Results count: {len(data.get('results', []))}")
            if data.get('results'):
                print(f"First result: {data['results'][0]}")
        else:
            print(f"V4 Fields Error body: {r.text}")

async def test_v4_court_filter():
    print(f"Testing V4 API with court filter...")
    async with httpx.AsyncClient() as client:
        # Test filtering by court only
        r = await client.get(
            "https://www.courtlistener.com/api/rest/v4/dockets/",
            params={
                "court": "nysd",  # Southern District of New York
                "fields": "id,case_name,date_filed,court,docket_number",
                "format": "json",
                "limit": 3,
            },
            headers={"Authorization": f"Token {token}"}
        )
        print(f"V4 Court Filter Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"V4 Court Filter Results count: {len(data.get('results', []))}")
            if data.get('results'):
                print(f"First result: {data['results'][0]}")
        else:
            print(f"V4 Court Filter Error body: {r.text}")

async def main():
    await test_v4_fields()
    print()
    await test_v4_court_filter()

if __name__ == "__main__":
    asyncio.run(main())