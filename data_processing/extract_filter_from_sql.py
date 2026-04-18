import json
import re
import os

def extract_filters_from_sql(sql):
    """
    Extracts filter candidates from SQL:
    - String literals (only those used with exact match '=')
    """
    # 1. Extract string literals that follow an equals sign
    strings = re.findall(r"=\s*'([^']*)'", sql)
    
    # We only return strings as requested by user
    return list(set(strings))

def analyze_entry(question, sql):
    """
    Analyzes one (question, sql) pair.
    """
    filters = extract_filters_from_sql(sql)
    
    found_in_question = []
    for f in filters:
        # Convert to string and check case-insensitive existence
        if str(f).lower() in question.lower():
            found_in_question.append(f)
            
    return {
        "filters": filters,
        "found": found_in_question,
        "total": len(filters),
        "matched": len(found_in_question)
    }

def main():
    datasets = [
        {"path": "other_benchmark/bird_dev.json", "sql_key": "SQL", "question_key": "question"},
        {"path": "other_benchmark/spider_dev.json", "sql_key": "query", "question_key": "question"},
        {"path": "data_mix_v5/test.final.jsonl", "sql_key": "SQL", "question_key": "question"}
    ]
    
    for ds_info in datasets:
        ds_path = ds_info["path"]
        sql_key = ds_info["sql_key"]
        question_key = ds_info["question_key"]
        
        if os.path.exists(ds_path):
            print(f"==================================================")
            print(f"Processing dataset: {ds_path}")
            print(f"==================================================")
            
            data = []
            with open(ds_path, 'r', encoding='utf-8') as f:
                if ds_path.endswith('.jsonl'):
                    for line in f:
                        if line.strip():
                            data.append(json.loads(line))
                else:
                    data = json.load(f)
                
            summary_stats = {
                "total_entries": 0,
                "perfect_matches": 0,  # All SQL filters exist in Question
                "partial_matches": 0,  # Some SQL filters exist in Question
                "no_filters": 0,       # SQL had no filters
                "zero_matches": 0      # SQL had filters but none in Question
            }
            
            total_ratio_sum = 0.0
            queries_with_filters = 0
            printed_examples = 0
            
            # Analyze all entries
            for i, entry in enumerate(data):
                q = entry.get(question_key, '')
                s = entry.get(sql_key, '')
                analysis = analyze_entry(q, s)
                
                summary_stats["total_entries"] += 1
                if analysis["total"] == 0:
                    summary_stats["no_filters"] += 1
                else:
                    ratio = analysis["matched"] / analysis["total"]
                    total_ratio_sum += ratio
                    queries_with_filters += 1
                    
                    if analysis["matched"] == analysis["total"]:
                        summary_stats["perfect_matches"] += 1
                    elif analysis["matched"] > 0:
                        summary_stats["partial_matches"] += 1
                        if printed_examples < 10:
                            print(f"[Example {printed_examples+1}]")
                            print(f"Q: {q}")
                            print(f"SQL: {s}")
                            print(f"Filters found: {analysis['filters']}")
                            print(f"Matched in Q: {analysis['found']}")
                            print(f"Result: {analysis['matched']}/{analysis['total']} matched\n")
                            printed_examples += 1
                    else:
                        summary_stats["zero_matches"] += 1
                        if printed_examples < 10:
                            print(f"[Example {printed_examples+1}]")
                            print(f"Q: {q}")
                            print(f"SQL: {s}")
                            print(f"Filters found: {analysis['filters']}")
                            print(f"Matched in Q: {analysis['found']}")
                            print(f"Result: {analysis['matched']}/{analysis['total']} matched\n")
                            printed_examples += 1
                    
            print("-" * 30)
            print(f"Summary for {ds_path}:")
            for key, val in summary_stats.items():
                print(f"  {key}: {val}")
                
            if queries_with_filters > 0:
                average_ratio = total_ratio_sum / queries_with_filters
                print(f"  Average Match Score (for queries with filters): {average_ratio:.2%}")
            else:
                print("  Average Match Score: No queries with filters found.")
            print("\n")
        else:
            print(f"Dataset not found: {ds_path}\n")

if __name__ == "__main__":
    main()