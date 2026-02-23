import json
with open('logs/execution_log.jsonl', encoding='utf-8') as f:
    lines = f.readlines()
print(f'Total lines: {len(lines)}')
# Check last few lines for final status
for line in lines[-3:]:
    data = json.loads(line)
    print(f"Deal: {data.get('deal_id')}, Status: {data.get('pipeline_status')}, Downloaded: {data.get('downloaded_files')}")
