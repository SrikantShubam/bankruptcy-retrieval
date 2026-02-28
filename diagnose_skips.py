import json

skipped = []
downloaded = []
not_found = []

with open('execution_log.jsonl') as f:
    for line in f:
        try:
            entry = json.loads(line.strip())
            if entry.get('event_type') == 'PIPELINE_TERMINAL':
                status = entry.get('pipeline_status')
                deal_id = entry.get('deal_id')
                if status == 'SKIPPED':
                    skipped.append(deal_id)
                elif status == 'DOWNLOADED':
                    downloaded.append(deal_id)
                elif status == 'NOT_FOUND':
                    not_found.append(deal_id)
        except:
            pass

print(f"DOWNLOADED ({len(downloaded)}): {downloaded}")
print(f"SKIPPED    ({len(skipped)}):    {skipped}")
print(f"NOT_FOUND  ({len(not_found)}): {not_found}")