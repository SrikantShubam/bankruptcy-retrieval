import httpx
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env

# Load environment variables
load_dotenv(find_root_env())

async def test_current_search():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "")
    if not token:
        print("No token found!")
        return

    headers = {"Authorization": f"Token {token}"}

    # Test with the exact same parameters we're using in our current implementation
    # Let's test with Yellow Corporation
    params = {
        "q": '"Yellow Corporation" short_description:"first day"',
        "type": "r",
        "available_only": "on",
        "order_by": "score desc",
        "filed_after": "2023-01-01",
        "filed_before": "2023-12-31",
        "court": "deb"
    }

    print(f"Testing current search approach with params: {params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params=params,
                headers=headers
            )

            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                print(f"Found {len(results)} results")

                # Check if any results have recap_documents
                for i, result in enumerate(results):
                    print(f"\n--- Result {i+1} ---")
                    print(f"Case Name: {result.get('caseName')}")
                    print(f"Date Filed: {result.get('dateFiled')}")

                    recap_docs = result.get('recap_documents', [])
                    print(f"Recap Documents: {len(recap_docs)} found")

                    for j, doc in enumerate(recap_docs[:2]):
                        print(f"  Document {j+1}:")
                        print(f"    Description: {doc.get('description', '')[:100]}...")
                        print(f"    Short Description: {doc.get('short_description', '')}")
                        print(f"    Filepath: {doc.get('filepath_local', '')}")
                        print(f"    Is Available: {doc.get('is_available', False)}")
                        print(f"    Page Count: {doc.get('page_count', 0)}")

            else:
                print(f"Request failed: {response.status_code}")
                print(response.text[:500])

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_current_search())