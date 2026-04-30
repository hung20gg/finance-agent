import json
import random
import os

def main():
    results_path = "../data/eval_train_results_openrouter_openai_gpt-oss-120b.jsonl"
    output_path = "../mcp-server/src/tools/example.md"
    
    examples = []
    
    if os.path.exists(results_path):
        with open(results_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                res = json.loads(line)
                
                # Check if total_score == 1.0
                score_obj = res.get("score", {})
                if score_obj.get("total_score") == 1.0:
                    messages = res.get("messages", [])
                    
                    question = None
                    sql_query = None
                    
                    # Get question
                    for msg in messages:
                        if msg.get("role") == "user":
                            question = msg.get("content")
                            break
                            
                    # Get SQL
                    for msg in reversed(messages):
                        if msg.get("role") == "assistant" and "tool_calls" in msg:
                            for tc in msg["tool_calls"]:
                                func = tc.get("function", {})
                                if func.get("name") == "execute_code":
                                    args_str = func.get("arguments", "{}")
                                    try:
                                        args = json.loads(args_str)
                                        if "query" in args:
                                            sql_query = args["query"]
                                            break
                                    except json.JSONDecodeError:
                                        pass
                            if sql_query:
                                break
                                
                    if question and sql_query:
                        examples.append({"question": question.strip(), "sql": sql_query.strip()})
    else:
        print(f"Error: Could not find {results_path}")
        return

    print(f"Found {len(examples)} examples with score 1.0.")
    
    # We want exactly 100 random examples (or less if not enough exist)
    random.seed(42) # For reproducibility
    sampled = random.sample(examples, min(100, len(examples)))
    
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in sampled:
            f.write(f"## {ex['question']}\n\n```sql\n{ex['sql']}\n```\n\n")
            
    print(f"Wrote {len(sampled)} examples to {output_path}")

if __name__ == "__main__":
    main()
