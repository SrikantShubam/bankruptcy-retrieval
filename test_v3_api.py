import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def test_v3_api():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Test V3 docket search
    docket_params = {
        "case_name__icontains": "Yellow Corporation",
        "date_filed__gte": "2023-01-01",
        "date_filed__lte": "2023-12-31",
        "court": "deb",
        "chapter": 11,
        "fields": "id,case_name,date_filed,court,docket_number"
    }

    print(f"Testing V3 docket search with params: {docket_params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            docket_response = await client.get(
                "https://www.courtlistener.com/api/rest/v3/dockets/",
                params=docket_params,
                headers=headers
            )

            print(f"Docket search status: {docket_response.status_code}")
            if docket_response.status_code == 200:
                docket_data = docket_response.json()
                print(f"Docket results: {docket_data.get('count', 0)} total")

                docket_results = docket_data.get("results", [])
                for i, docket in enumerate(docket_results[:3]):
                    print(f"\n--- Docket {i+1} ---")
                    print(f"ID: {docket.get('id')}")
                    print(f"Case Name: {docket.get('case_name')}")
                    print(f"Date Filed: {docket.get('date_filed')}")
                    print(f"Court: {docket.get('court')}")
                    print(f"Docket Number: {docket.get('docket_number')}")

                    # If we found a docket, try getting docket entries
                    if docket.get("id"):
                        entry_params = {
                            "docket": docket["id"],
                            "description__icontains": "first day",
                            "date_filed__gte": "2023-01-01",
                            "order_by": "date_filed",
                            "page_size": 5,
                            "fields": "id,description,date_filed,recap_documents"
                        }

                        print(f"\nGetting docket entries for docket {docket['id']}")
                        entry_response = await client.get(
                            "https://www.courtlistener.com/api/rest/v3/docket-entries/",
                            params=entry_params,
                            headers=headers
                        )

                        print(f"Entry search status: {entry_response.status_code}")
                        if entry_response.status_code == 200:
                            entry_data = entry_response.json()
                            entry_results = entry_data.get("results", [])

                            print(f"Entry results: {len(entry_results)} found")

                            for j, entry in enumerate(entry_results[:2]):
                                print(f"\n--- Entry {j+1} ---")
                                print(f"ID: {entry.get('id')}")
                                print(f"Description: {entry.get('description')}")
                                print(f"Date Filed: {entry.get('date_filed')}")
                                print(f"Recap Documents: {entry.get('recap_documents')}")

                                # Check if we have recap documents
                                recap_docs = entry.get('recap_documents', [])
                                if recap_docs:
                                    print(f"Found {len(recap_docs)} recap documents")

                                    # Get details for the first recap document
                                    doc_id = recap_docs[0]
                                    if isinstance(doc_id, dict):
                                        doc_id = doc_id.get('id') or doc_id.get('pk')

                                    if doc_id:
                                        print(f"Getting details for document {doc_id}")
                                        doc_response = await client.get(
                                            f"https://www.courtlistener.com/api/rest/v3/recap-documents/{doc_id}/",
                                            headers=headers
                                        )

                                        print(f"Document details status: {doc_response.status_code}")
                                        if doc_response.status_code == 200:
                                            doc_data = doc_response.json()
                                            print(f"Document data: {doc_data}")
                        else:
                            print(f"Entry search failed: {entry_response.text[:500]}")

            else:
                print(f"Docket search failed: {docket_response.text[:500]}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_v3_api())