#!/usr/bin/env python3
"""
Debug script to test gatekeeper evaluation
"""
import asyncio
import sys
sys.path.insert(0, '.')

from shared.gatekeeper import LLMGatekeeper, CandidateDocument
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def main():
    gatekeeper = LLMGatekeeper()
    
    # Test candidate from BlockFi
    candidate = CandidateDocument(
        deal_id="blockfi-2022",
        source="courtlistener",
        docket_entry_id="12345",
        docket_title="Declaration of [Name] in Support of Chapter 11 Petition",
        filing_date="2022-07-01",
        attachment_descriptions=[],
        resolved_pdf_url="https://example.com/test.pdf"
    )
    
    print(f"Testing gatekeeper with candidate:")
    print(f"  Deal ID: {candidate.deal_id}")
    print(f"  Title: {candidate.docket_title}")
    print()
    
    try:
        result = await gatekeeper.evaluate(candidate)
        print(f"Result:")
        print(f"  Verdict: {result.verdict}")
        print(f"  Score: {result.score}")
        print(f"  Reasoning: {result.reasoning}")
        print(f"  Error: {result.error}")
        print(f"  Model: {result.model_used}")
        print(f"  Latency: {result.latency_ms}ms")
    except Exception as e:
        print(f"Exception during evaluation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
