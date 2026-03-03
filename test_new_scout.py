#!/usr/bin/env python3
"""Test the new find_document_for_deal function"""

import asyncio
import sys
sys.path.insert(0, '../bankruptcy-retrieval')

from scout import find_document_for_deal

async def main():
    print("Testing new find_document_for_deal function")
    print("=" * 50)

    # Test with WeWork
    result = await find_document_for_deal("WeWork", 2023, "S.D.N.Y.")

    if result:
        print("Found document:")
        print(f"  Title: {result['docket_title'][:60]}")
        print(f"  Date: {result['filing_date']}")
        print(f"  URL: {result['resolved_pdf_url']}")
        print(f"  API calls: {result['api_calls_consumed']}")
    else:
        print("No document found")

    print("\n" + "=" * 50)
    print("Test complete")

if __name__ == "__main__":
    asyncio.run(main())