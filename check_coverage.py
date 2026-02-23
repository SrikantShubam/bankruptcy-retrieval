import json
with open('../bankruptcy-retrieval/data/deals_dataset.json') as f:
    deals = json.load(f)

has_id = [d for d in deals if d.get('pacer_case_id') and not d.get('already_processed')]
no_id  = [d for d in deals if not d.get('pacer_case_id') and not d.get('already_processed')]
has_agent = [d for d in no_id if d.get('claims_agent')]

print(f'Active deals with pacer_case_id:  {len(has_id)}')
print(f'Active deals without ID:           {len(no_id)}')
print(f'  Of those, have claims_agent:     {len(has_agent)}')
print(f'  Of those, have neither:          {len(no_id) - len(has_agent)}')
