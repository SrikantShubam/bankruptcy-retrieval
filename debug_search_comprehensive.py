import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def debug_search_comprehensive():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Try a broader search for recent bankruptcy filings
    companies_to_test = [
        "WeWork",
        "Rite Aid",
        "Yellow Corporation",
        "SVB",
        "BlockFi"
    ]

    for company in companies_to_test:
        print(f"\n=== Searching for {company} ===")

        # Try different search approaches
        search_variations = [
            f'"{company}" chapter:11',
            f'"{company}" "first day"',
            f'"{company}" "chapter 11"',
            f'"{company}" bankruptcy'
        ]

        for variation in search_variations:
            params = {
                "q": variation,
                "type": "r",
                "order_by": "dateFiled desc",
                "available_only": "on",  # Only available documents
                "page_size": 5
            }

            print(f"  Query: {variation}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.get(
                        "https://www.courtlistener.com/api/rest/v4/search/",
                        params=params,
                        headers=headers
                    )

                    if response.status_code == 200:
                        data = response.json()
                        results = data.get("results", [])

                        available_docs = [r for r in results if r.get("filepath_local") and r.get("is_available")]
                        print(f"    Found {len(results)} total results, {len(available_docs)} available")

                        if available_docs:
                            print(f"    *** AVAILABLE DOCUMENTS FOUND FOR '{company}' ***")
                            for i, doc in enumerate(available_docs[:2]):
                                print(f"      Doc {i+1}:")
                                print(f"        Title: {doc.get('short_description', '') or doc.get('caseName', '')}")
                                print(f"        Date: {doc.get('dateFiled', '')}")
                                print(f"        Filepath: {doc.get('filepath_local', '')}")
                                print(f"        Available: {doc.get('is_available', '')}")
                    else:
                        print(f"    Status {response.status_code}: {response.text[:100]}")

                except Exception as e:
                    print(f"    Error: {e}")
                    continue

            # Small delay to be respectful
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_search_comprehensive())