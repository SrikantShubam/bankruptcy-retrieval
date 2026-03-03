import httpx, asyncio, os
from dotenv import load_dotenv
load_dotenv('.env')

async def check():
    token = os.environ.get('COURTLISTENER_API_TOKEN', 'MISSING')
    print(f"Token present: {token != 'MISSING'}")
    print(f"Token prefix: {token[:8]}...")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://www.courtlistener.com/api/rest/v4/search/",
            params={"q": '"WeWork" short_description:"first day"', "type": "r", "available_only": "on"},
            headers={"Authorization": f"Token {token}"}
        )
    print(f"V4 search status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Result count: {data.get('count')}")
        for res in data.get('results', [])[:3]:
            print(f"  - {res.get('caseName')} | {res.get('short_description','')[:60]}")
            print(f"    available={res.get('is_available')} filepath={bool(res.get('filepath_local'))}")

asyncio.run(check())