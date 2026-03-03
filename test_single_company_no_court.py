import asyncio
import os
from dotenv import load_dotenv
load_dotenv('.env')

from scout import find_document_for_deal

async def test_single_company():
    # Test with a known bankruptcy case without court filter
    result = await find_document_for_deal(
        company_name="WeWork",
        filing_year=2023,
        court=""  # No court filter
    )
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test_single_company())