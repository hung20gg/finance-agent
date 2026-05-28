import json
import re

def load_json_with_fixes(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple fix: replace unescaped newlines inside strings with \n
    # A more robust way is to just find literal newlines between quotes.
    # Let's try simple replacement for the specific error
    # but actually, python's json handles newlines if we use strict=False
    try:
        data = json.loads(content, strict=False)
        print("Loaded strict=False successfully! Length:", len(data))
    except Exception as e:
        print("Failed with strict=False:", e)

load_json_with_fixes('data_processing/multi-turn/multi-turn-v1.jsonl')
