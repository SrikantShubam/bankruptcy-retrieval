import json
with open('../bankruptcy-retrieval/data/deals_dataset.json') as f:
    deals = json.load(f)

# Find WeWork
for d in deals:
    if 'wework' in d.get('deal_id', '').lower():
        print(json.dumps(d, indent=2))
        break
