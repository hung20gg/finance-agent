import json
import os

def clean_data():
    sharegpt_path = "/home/quanghung20gg/Documents/new/kltn/LlamaFactory/data/output_sharegpt_clean.jsonl"
    train_path = "/home/quanghung20gg/Documents/new/kltn/finance-agent/data_processing/data_mix_v5/train.cleaned.jsonl"
    val_path = "/home/quanghung20gg/Documents/new/kltn/finance-agent/data_processing/data_mix_v5/val.cleaned.jsonl"

    # 1. Collect ShareGPT IDs
    print(f"Reading ShareGPT IDs from {sharegpt_path}...")
    sharegpt_ids = set()
    if os.path.exists(sharegpt_path):
        with open(sharegpt_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    sharegpt_ids.add(data['id'])
                except Exception as e:
                    print(f"Error parsing line in ShareGPT: {e}")
    else:
        print(f"Warning: ShareGPT file not found at {sharegpt_path}")

    print(f"Found {len(sharegpt_ids)} unique IDs in ShareGPT.")

    # 2. Process train.cleaned.jsonl
    print(f"Processing {train_path}...")
    train_data = []
    if os.path.exists(train_path):
        with open(train_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    if data['id'] not in sharegpt_ids:
                        train_data.append(line)
                except Exception as e:
                    print(f"Error parsing line in Train: {e}")
        
        print(f"Train data: {len(train_data)} examples remaining after filtering (ignored ShareGPT examples).")
        
        # Write back
        with open(train_path, 'w', encoding='utf-8') as f:
            for line in train_data:
                f.write(line)
        print(f"Updated {train_path} successfully.")
    else:
        print(f"Error: Train file not found at {train_path}")

    # 3. Process val.cleaned.jsonl (only take a half)
    print(f"Processing {val_path}...")
    if os.path.exists(val_path):
        val_lines = []
        with open(val_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    val_lines.append(line)
        
        half_count = len(val_lines) // 2
        print(f"Val data: {len(val_lines)} total examples. Reducing to {half_count}.")
        
        val_lines_reduced = val_lines[:half_count]
        
        with open(val_path, 'w', encoding='utf-8') as f:
            for line in val_lines_reduced:
                f.write(line)
        print(f"Updated {val_path} successfully.")
    else:
        print(f"Error: Val file not found at {val_path}")

if __name__ == "__main__":
    clean_data()
