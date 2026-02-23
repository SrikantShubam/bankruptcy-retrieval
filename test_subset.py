import json

with open('../bankruptcy-retrieval/data/deals_dataset.json', 'r') as f:
    deals = json.load(f)

subset_ids = ["rite-aid-2023", "bed-bath-beyond-2023", "yellow-corp-2023", "medical-decoy-c"]
subset = [d for d in deals if d["deal_id"] in subset_ids]

with open('deals_dataset_subset.json', 'w') as out:
    json.dump(subset, out, indent=2)
