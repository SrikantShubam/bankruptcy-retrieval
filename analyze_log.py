import json
with open('logs/execution_log.jsonl', encoding='utf-8') as f:
    lines = f.readlines()

# Get final status for each deal (last entry)
deals = {}
for line in lines:
    data = json.loads(line)
    deal_id = data.get('deal_id')
    deals[deal_id] = data

# Count statuses
statuses = {}
for deal_id, data in deals.items():
    status = data.get('pipeline_status', 'unknown')
    statuses[status] = statuses.get(status, 0) + 1
    
print('Pipeline statuses:')
for s, c in statuses.items():
    print(f'  {s}: {c}')

# Check DOWNLOADED deals
downloaded = [d for d, data in deals.items() if data.get('pipeline_status') == 'DOWNLOADED']
print(f'\nDeals with DOWNLOADED status: {len(downloaded)}')
print(f'First few: {downloaded[:5]}')
