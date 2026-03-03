import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def check_recap_documents_v2():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Search for Yellow Corporation to get docket information
    search_params = {
        "q": 'caseName:"Yellow Corporation" AND chapter:11',
        "type": "r",
        "order_by": "dateFiled desc",
        "page_size": 1
    }

    print(f"Searching with params: {search_params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First, search to get case information
            search_response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=search_params,
                headers=headers
            )

            if search_response.status_code == 200:
                search_data = search_response.json()
                results = search_data.get("results", [])

                if results:
                    result = results[0]
                    print("Search result:")
                    print(f"  Case Name: {result.get('caseName')}")
                    print(f"  Date Filed: {result.get('dateFiled')}")
                    print(f"  Docket ID: {result.get('docket_id')}")

                    # Get the docket ID from the search result
                    docket_id = result.get('docket_id')

                    if docket_id:
                        print(f"\nFound docket ID: {docket_id}")

                        # Get docket entries for this docket
                        entries_params = {
                            "docket_id": docket_id,
                            "order_by": "date_filed",
                            "page_size": 10
                        }

                        print(f"Getting docket entries with params: {entries_params}")
                        entries_response = await client.get(
                            "https://www.courtlistener.com/api/rest/v4/docket-entries/",
                            params=entries_params,
                            headers=headers
                        )

                        if entries_response.status_code == 200:
                            entries_data = entries_response.json()
                            entries_results = entries_data.get("results", [])

                            print(f"Found {len(entries_results)} docket entries")

                            # Look for entries with "first day" or similar terms in the description
                            first_day_entries = []
                            for entry in entries_results:
                                desc = entry.get('description', '').lower()
                                if any(term in desc for term in ['first day', 'declaration', 'dip', 'cash collateral']):
                                    first_day_entries.append(entry)

                            print(f"Found {len(first_day_entries)} relevant entries")

                            for i, entry in enumerate(first_day_entries[:3]):  # Show first 3 relevant entries
                                print(f"\n--- Relevant Entry {i+1} ---")
                                print(f"ID: {entry.get('id')}")
                                print(f"Description: {entry.get('description')}")
                                print(f"Date Filed: {entry.get('date_filed')}")

                                # Get recap documents for this entry
                                if entry.get("id"):
                                    docs_params = {
                                        "docket_entry_id": entry["id"],
                                        "page_size": 3
                                    }

                                    docs_response = await client.get(
                                        "https://www.courtlistener.com/api/rest/v4/recap-documents/",
                                        params=docs_params,
                                        headers=headers
                                    )

                                    if docs_response.status_code == 200:
                                        docs_data = docs_response.json()
                                        docs_results = docs_data.get("results", [])

                                        print(f"  Found {len(docs_results)} recap documents")

                                        for j, doc in enumerate(docs_results):
                                            print(f"    Document {j+1}:")
                                            print(f"      ID: {doc.get('id')}")
                                            print(f"      Description: {doc.get('description')}")
                                            print(f"      Page Count: {doc.get('page_count')}")
                                            print(f"      Filepath: {doc.get('filepath_local')}")
                                            print(f"      Is Available: {doc.get('is_available')}")
                                            print(f"      Download URL: {doc.get('download_url')}")

                                            # Check if this document is available for download
                                            if doc.get('filepath_local') and doc.get('is_available'):
                                                print(f"      *** AVAILABLE FOR DOWNLOAD ***")
                        else:
                            print(f"Entries search failed: {entries_response.status_code}")
                            print(entries_response.text[:500])
                    else:
                        print("No docket ID found in search result")
                else:
                    print("No search results found")
            else:
                print(f"Search failed: {search_response.status_code}")
                print(search_response.text[:500])

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_recap_documents_v2())