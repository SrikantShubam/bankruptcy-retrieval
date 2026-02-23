"""discover_v4_params.py — run once, outputs confirmed V4 param list"""
import httpx
import asyncio
import os
import json
import sys

sys.path.insert(0, '../bankruptcy-retrieval')
from shared.config import find_root_env
from dotenv import load_dotenv

load_dotenv(find_root_env())

TOKEN = os.environ.get('COURTLISTENER_API_TOKEN', 'NOT_FOUND')
if TOKEN == 'NOT_FOUND':
    print("ERROR: COURTLISTENER_API_TOKEN not found in environment")
    sys.exit(1)

BASE = "https://www.courtlistener.com/api/rest/v4"
HEADERS = {"Authorization": f"Token {TOKEN}"}

PARAMS_TO_TEST = [
    # Dockets endpoint
    ("dockets", "case_name"),
    ("dockets", "case_name__icontains"),
    ("dockets", "case_name__startswith"),
    ("dockets", "date_filed__gte"),
    ("dockets", "date_filed__lte"),
    ("dockets", "court"),
    ("dockets", "court__id"),
    ("dockets", "chapter"),
    ("dockets", "docket_number"),
    ("dockets", "docket_number__icontains"),
    ("dockets", "nature_of_suit"),
    ("dockets", "pacer_case_id"),
    # Docket entries endpoint
    ("docket-entries", "docket"),
    ("docket-entries", "docket__id"),
    ("docket-entries", "description__icontains"),
    ("docket-entries", "description__contains"),
    ("docket-entries", "date_filed__gte"),
    ("docket-entries", "date_filed__lte"),
    ("docket-entries", "entry_number"),
]

async def test_param(endpoint, param_name):
    url = f"{BASE}/{endpoint}/"
    # Use a dummy value — we just want to know if param is accepted
    test_value = "2023-01-01" if "date" in param_name else "test"
    params = {param_name: test_value, "fields": "id", "cursor": None}
    params = {k: v for k, v in params.items() if v is not None}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, params=params, headers=HEADERS)
    except httpx.ReadTimeout:
        return (endpoint, param_name, "TIMEOUT")
    except Exception as e:
        return (endpoint, param_name, f"EXCEPTION: {type(e).__name__}")

    if r.status_code == 200:
        return (endpoint, param_name, "VALID")
    elif r.status_code == 400:
        try:
            body = r.json()
            unknown = body.get("unknown_params", [])
            if param_name in unknown:
                return (endpoint, param_name, "REJECTED")
            else:
                return (endpoint, param_name, f"400-OTHER: {body}")
        except:
            return (endpoint, param_name, f"400-PARSE-ERROR: {r.text[:100]}")
    elif r.status_code == 403:
        return (endpoint, param_name, "403-FORBIDDEN")
    else:
        return (endpoint, param_name, f"HTTP-{r.status_code}")

async def main():
    results = []
    print(f"Testing {len(PARAMS_TO_TEST)} parameters on V4 API...")
    print(f"Token available: {bool(TOKEN)}")

    for endpoint, param in PARAMS_TO_TEST:
        result = await test_param(endpoint, param)
        results.append(result)
        status = result[2]
        print(f"  [{status:20s}] /api/rest/v4/{endpoint}/?{param}=...")
        await asyncio.sleep(0.2)  # be polite

    valid = [(e, p) for e, p, s in results if s == "VALID"]
    rejected = [(e, p) for e, p, s in results if s == "REJECTED"]

    print(f"\n✓ VALID params ({len(valid)}):")
    for e, p in valid:
        print(f"    {e}: {p}")

    print(f"\n✗ REJECTED params ({len(rejected)}):")
    for e, p in rejected:
        print(f"    {e}: {p}")

    other = [(e, p, s) for e, p, s in results if s not in ["VALID", "REJECTED"]]
    if other:
        print(f"\n⚠️  OTHER results ({len(other)}):")
        for e, p, s in other:
            print(f"    {e}/{p}: {s}")

    # Save results
    with open("v4_param_discovery.json", "w") as f:
        json.dump([{"endpoint": e, "param": p, "status": s} for e, p, s in results], f, indent=2)

    print(f"\nResults saved to v4_param_discovery.json")

if __name__ == "__main__":
    asyncio.run(main())