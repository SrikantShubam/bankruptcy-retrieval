import httpx
import asyncio

async def smoke_test():
    # Test V3 endpoint
    SEARCH_URL = 'https://www.courtlistener.com/api/rest/v3/search/'
    async with httpx.AsyncClient() as client:
        # Without token - should get 401/403, not 400
        r = await client.get(
            SEARCH_URL,
            params={
                'q': 'WeWork first day declaration',
                'type': 'r',
                'filed_after': '2023-01-01',
                'filed_before': '2023-12-31',
                'order_by': 'score desc',
                'page_size': 3,
            }
        )
        print(f"V3 Status (no token): {r.status_code}")
        if r.status_code != 400:
            print("SUCCESS: Not a 400 error - V3 endpoint works!")
        else:
            print(f"FAILURE: Got 400 error: {r.text[:500]}")
        
    # Also test V4 endpoint to show the difference
    V4_URL = 'https://www.courtlistener.com/api/rest/v4/search/'
    async with httpx.AsyncClient() as client:
        r2 = await client.get(
            V4_URL,
            params={
                'q': 'WeWork first day declaration',
                'type': 'r',
                'filed_after': '2023-01-01',
                'filed_before': '2023-12-31',
                'order_by': 'score desc',
                'page_size': 3,
            }
        )
        print(f"V4 Status (no token): {r2.status_code}")
        if r2.status_code == 400:
            print("CONFIRMED: V4 returns 400 for 'q' parameter (as expected)")
            print(f"V4 Error: {r2.text[:200]}")

asyncio.run(smoke_test())
