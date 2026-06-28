import time
import os
import sys
import psutil
from pathlib import Path

# Add repo root and mcp-server/src to sys.path before other imports
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "mcp-server" / "src"))

from env_config import load_env_config
load_env_config()

from client import PostgresClient
from tools.fuzzy_search_financial_metrics import get_search_backend, load_search_config, load_all_tables

def run_evaluation():
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / 1024 / 1024
    print(f"Initial Memory Usage: {mem_before:.2f} MB")
    
    # Initialize DB client and load config
    client = PostgresClient(postgres_url=os.environ.get("POSTGRES_URL"))
    config_path = os.path.join(os.path.dirname(__file__), "./tools/fuzzy_search_config.json")
    config = load_search_config(config_path)
    entities_config = config["searchable_entities"]
    
    # 1. Benchmark Data Loading Time and RAM consumption
    t0 = time.time()
    data_map = load_all_tables(client, entities_config)
    load_time = time.time() - t0
    mem_after = process.memory_info().rss / 1024 / 1024
    
    print(f"Data Loaded in {load_time:.2f}s")
    print(f"Memory Usage After Load: {mem_after:.2f} MB (Delta: {mem_after - mem_before:.2f} MB)")
    
    # 2. Benchmark Query Latency
    backend = get_search_backend(config.get("search_backend", "rapidfuzz"))
    
    test_queries = [
        ("company", "Vinamilk"),
        ("exchange", "HOSE"),
        ("macro_indicator", "GDP"),
        # Warn: Searching financial_statement (2.3M rows) with iterrows will take a long time!
        ("financial_statement", "VNM")
    ]
    
    print("\n--- Query Latency Benchmark ---")
    for field, query in test_queries:
        df = data_map.get(field)
        if df is None or df.empty:
            print(f"[{field}] Table is empty or not loaded. Skipping.")
            continue
            
        cfg = entities_config[field]
        search_columns = cfg["search_columns"]
        threshold = cfg.get("threshold", 50)
        limit = cfg.get("limit", 10)
        
        t0 = time.time()
        result_df = backend.search(df, query, search_columns, threshold, limit)
        latency = time.time() - t0
        
        num_results = len(result_df) if result_df is not None else 0
        print(f"Field: '{field}' (size: {len(df):,} rows) | Query: '{query}'")
        print(f"  -> Latency: {latency:.4f}s | Results found: {num_results}")

if __name__ == "__main__":
    run_evaluation()
