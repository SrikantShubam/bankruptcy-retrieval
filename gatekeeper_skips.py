import json

with open('execution_log.jsonl') as f:
    for line in f:
        try:
            entry = json.loads(line.strip())
            if entry.get('event_type') == 'GATEKEEPER_DECISION' and entry.get('llm_verdict') == 'SKIP':
                print(f"{entry.get('deal_id'):30s} score={entry.get('llm_score'):.2f} title={entry.get('docket_title','')[:70]}")
        except:
            pass