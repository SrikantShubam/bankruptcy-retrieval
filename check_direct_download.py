import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def check_direct_download():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Try searching for documents that might have direct download URLs
    search_params = {
        "q": '"Yellow Corporation" AND "first day"',
        "type": "r",
        "order_by": "dateFiled desc",
        "page_size": 20
    }

    print(f"Searching with params: {search_params}")

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

                print(f"Found {len(results)} results")

                # Look for results with any kind of URL or filepath information
                for i, result in enumerate(results):
                    print(f"\n--- Result {i+1} ---")
                    print(f"Case Name: {result.get('caseName')}")
                    print(f"Short Description: {result.get('short_description')}")
                    print(f"Date Filed: {result.get('dateFiled')}")
                    print(f"Docket ID: {result.get('docket_id')}")
                    print(f"Entry ID: {result.get('entry_id')}")
                    print(f"Document ID: {result.get('document_id')}")
                    print(f"Is Available: {result.get('is_available')}")
                    print(f"Filepath Local: {result.get('filepath_local')}")
                    print(f"Download URL: {result.get('download_url')}")
                    print(f"Absolute URL: {result.get('absolute_url')}")

                    # Check if we can construct a download URL
                    doc_id = result.get('document_id')
                    if doc_id:
                        constructed_url = f"https://www.courtlistener.com/api/rest/v4/recap-document/{doc_id}/"
                        print(f"Constructed URL: {constructed_url}")

                # Let's also try a broader search for any available bankruptcy documents
                broad_search_params = {
                    "q": "chapter:11",
                    "type": "r",
                    "available_only": "on",
                    "order_by": "dateFiled desc",
                    "page_size": 10
                }

                print(f"\n\nTrying broad search with params: {broad_search_params}")
                broad_response = await client.get(
                    "https://www.courtlistener.com/api/rest/v4/search/",
                    params=broad_search_params,
                    headers=headers
                )

                if broad_response.status_code == 200:
                    broad_data = broad_response.json()
                    broad_results = broad_data.get("results", [])

                    print(f"Found {len(broad_results)} broadly available bankruptcy documents")

                    available_count = 0
                    for i, result in enumerate(broad_results):
                        if result.get('filepath_local') and result.get('is_available'):
                            available_count += 1
                            print(f"\n--- Available Document {available_count} ---")
                            print(f"Case Name: {result.get('caseName')}")
                            print(f"Short Description: {result.get('short_description')}")
                            print(f"Date Filed: {result.get('dateFiled')}")
                            print(f"Filepath Local: {result.get('filepath_local')}")
                            print(f"Is Available: {result.get('is_available')}")

                            if available_count >= 5:  # Show first 5 available documents
                                break

                    if available_count == 0:
                        print("No available documents found in broad search either")

            else:
                print(f"Search failed: {search_response.status_code}")
                print(search_response.text[:500])

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_direct_download())