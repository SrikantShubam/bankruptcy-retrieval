import re
with open('nodes.py', encoding='utf-8') as f:
    content = f.read()

# Find log_node
log_match = re.search(r'async def log_node\(.*?\):.*?(?=\n(?:async )?def |\n# ──|\Z)', content, re.DOTALL)
if log_match:
    print('=== log_node ===')
    print(log_match.group()[:500])

# Find telemetry_node
telem_match = re.search(r'async def telemetry_node\(.*?\):.*?(?=\n(?:async )?def |\n# ──|\Z)', content, re.DOTALL)
if telem_match:
    print('=== telemetry_node ===')
    print(telem_match.group()[:500])
