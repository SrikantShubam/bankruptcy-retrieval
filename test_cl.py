import httpx
import json
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        response = await client.get('https://www.courtlistener.com/api/rest/v4/search/', 
            params={
                'q': '"WeWork" (short_description:"first day" OR short_description:"DIP")',
                'type': 'r',
                'available_only': 'on',
                'filed_after': '2023-01-01',
                'filed_before': '2023-12-31',
            }
        )
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data.get('results', [])[:1], indent=2))
        else:
            print(f"Error: {response.status_code} - {response.text}")

asyncio.run(main())
