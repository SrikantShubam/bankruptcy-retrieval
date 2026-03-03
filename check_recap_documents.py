import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def check_recap_documents():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # First, let's get a specific docket entry ID from our previous search
    # Let's search for Yellow Corporation again and get a docket entry ID
    search_params = {
        "q": 'caseName:"Yellow Corporation" AND chapter:11',
        "type": "r",
        "order_by": "dateFiled desc",
        "page_size": 1
    }

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

                if results:
                    # Get the first result
                    result = results[0]
                    print("Search result:")
                    print(f"  Case Name: {result.get('caseName')}")
                    print(f"  Date Filed: {result.get('dateFiled')}")

                    # Now let's try to get recap documents for this case
                    # We need to find the docket ID first
                    docket_params = {
                        "case_name": "Yellow Corporation",
                        "chapter": 11,
                        "page_size": 1
                    }

                    print(f"\nSearching for docket with params: {docket_params}")
                    docket_response = await client.get(
                        "https://www.courtlistener.com/api/rest/v4/dockets/",
                        params=docket_params,
                        headers=headers
                    )

                    if docket_response.status_code == 200:
                        docket_data = docket_response.json()
                        docket_results = docket_data.get("results", [])

                        if docket_results:
                            docket = docket_results[0]
                            docket_id = docket.get("id")
                            print(f"Found docket ID: {docket_id}")

                            # Now get docket entries for this docket
                            if docket_id:
                                entries_params = {
                                    "docket_id": docket_id,
                                    "page_size": 5
                                }

                                print(f"\nGetting docket entries for docket {docket_id}")
                                entries_response = await client.get(
                                    "https://www.courtlistener.com/api/rest/v4/docket-entries/",
                                    params=entries_params,
                                    headers=headers
                                )

                                if entries_response.status_code == 200:
                                    entries_data = entries_response.json()
                                    entries_results = entries_data.get("results", [])

                                    print(f"Found {len(entries_results)} docket entries")

                                    for i, entry in enumerate(entries_results):
                                        print(f"\n--- Docket Entry {i+1} ---")
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
                        else:
                            print("No dockets found")
                    else:
                        print(f"Docket search failed: {docket_response.status_code}")
                        print(docket_response.text[:500])
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
    asyncio.run(check_recap_documents())