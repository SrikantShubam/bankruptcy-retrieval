import asyncio
import os
from dotenv import load_dotenv
load_dotenv('.env')

from scout import find_document_for_deal

# Mock the find_document_for_deal function to return a simulated result
async def mock_find_document_for_deal(company_name, filing_year, court):
    # Simulate finding a document
    return {
        "docket_entry_id": "12345",
        "docket_title": "First Day Declaration - WeWork",
        "filing_date": "2023-11-06",
        "attachment_descriptions": [],
        "resolved_pdf_url": "https://storage.courtlistener.com/mock/path/to/document.pdf",
        "api_calls_consumed": 3,
        "source": "courtlistener",
    }

async def test_mock_success():
    # Temporarily replace the function
    import scout
    original_func = scout.find_document_for_deal
    scout.find_document_for_deal = mock_find_document_for_deal

    try:
        # Test with a known bankruptcy case
        result = await mock_find_document_for_deal(
            company_name="WeWork",
            filing_year=2023,
            court="D.N.J."
        )
        print(f"Mock result: {result}")
        print("Mock test successful!")
    finally:
        # Restore the original function
        scout.find_document_for_deal = original_func

if __name__ == "__main__":
    asyncio.run(test_mock_success())