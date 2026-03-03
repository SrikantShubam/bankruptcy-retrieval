# save as debug_gatekeeper.py and run: python debug_gatekeeper.py
import asyncio, sys, traceback
sys.path.insert(0, '../bankruptcy-retrieval')
from shared.gatekeeper import LLMGatekeeper
from shared.config import OPENROUTER_API_KEY, NVIDIA_NIM_API_KEY, GATEKEEPER_PROVIDER

print(f"GATEKEEPER_PROVIDER: {GATEKEEPER_PROVIDER}")
print(f"OPENROUTER_API_KEY present: {bool(OPENROUTER_API_KEY)}")
print(f"NVIDIA_NIM_API_KEY present: {bool(NVIDIA_NIM_API_KEY)}")

class FakeCandidate:
    deal_id = "wework-2023"
    source = "courtlistener"
    docket_entry_id = "123"
    docket_title = "Declaration of David Tolley in Support of First Day Motions"
    filing_date = "2023-11-06"
    attachment_descriptions = []
    resolved_pdf_url = "https://storage.courtlistener.com/recap/test.pdf"

async def test():
    try:
        gk = LLMGatekeeper()
        result = await gk.evaluate(FakeCandidate())
        print(f"verdict={result.verdict} score={result.score}")
        print(f"reasoning={result.reasoning}")
    except Exception as e:
        print(f"EXCEPTION TYPE: {type(e).__name__}")
        print(f"EXCEPTION: {e}")
        traceback.print_exc()

asyncio.run(test())