import json
with open('../bankruptcy-retrieval/data/deals_dataset.json', 'r') as f:
    deals = json.load(f)

for d in deals:
    if d['deal_id'] in ['bed-bath-beyond-2023', 'yellow-corp-2023']:
        print(f"{d['deal_id']} -> claims_agent: {d.get('claims_agent')}")
