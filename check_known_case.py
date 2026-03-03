import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def check_known_case():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Try searching for a well-known recent bankruptcy case that should have documents
    # Let's try FTX since it was a major bankruptcy case
    search_params = {
        "q": '"FTX" chapter:11',
        "type": "r",
        "order_by": "dateFiled desc",
        "page_size": 20
    }

    print(f"Searching for FTX with params: {search_params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            search_response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=search_params,
                headers=headers
            )

            if search_response.status_code == 200:
                search_data = search_response.json()
                results = search_data.get("results", [])

                print(f"Found {len(results)} FTX results")

                # Check for any results with availability info
                for i, result in enumerate(results):
                    print(f"\n--- FTX Result {i+1} ---")
                    print(f"Case Name: {result.get('caseName')}")
                    print(f"Short Description: {result.get('short_description')}")
                    print(f"Date Filed: {result.get('dateFiled')}")
                    print(f"Is Available: {result.get('is_available')}")
                    print(f"Filepath Local: {result.get('filepath_local')}")
                    print(f"Download URL: {result.get('download_url')}")

                # Let's also try searching for any document with a specific short description
                doc_search_params = {
                    "q": 'short_description:"first day"',
                    "type": "r",
                    "order_by": "dateFiled desc",
                    "page_size": 10
                }

                print(f"\n\nSearching for 'first day' documents with params: {doc_search_params}")
                doc_response = await client.get(
                    "https://www.courtlistener.com/api/rest/v4/search/",
                    params=doc_search_params,
                    headers=headers
                )

                if doc_response.status_code == 200:
                    doc_data = doc_response.json()
                    doc_results = doc_data.get("results", [])

                    print(f"Found {len(doc_results)} 'first day' documents")

                    # Check for any results with availability info
                    for i, result in enumerate(doc_results):
                        print(f"\n--- First Day Document {i+1} ---")
                        print(f"Case Name: {result.get('caseName')}")
                        print(f"Short Description: {result.get('short_description')}")
                        print(f"Date Filed: {result.get('dateFiled')}")
                        print(f"Is Available: {result.get('is_available')}")
                        print(f"Filepath Local: {result.get('filepath_local')}")
                        print(f"Download URL: {result.get('download_url')}")

                        # Break after first 5 results
                        if i >= 4:
                            break
                else:
                    print(f"Document search failed: {doc_response.status_code}")

            else:
                print(f"FTX search failed: {search_response.status_code}")
                print(search_response.text[:500])

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_known_case())