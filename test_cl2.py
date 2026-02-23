import httpx
import json
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        response = await client.get('https://www.courtlistener.com/api/rest/v4/search/', 
            params={
                'q': '"Yellow Corporation" (short_description:"first day" OR short_description:"DIP")',
                'type': 'r',
                'available_only': 'on'
            }
        )
        if response.status_code == 200:
            print(json.dumps(response.json().get('results', [])[:1], indent=2))
        else:
            print(response.status_code)

asyncio.run(main())
