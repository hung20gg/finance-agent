import json
import re


# -----------------------
# LOADERS
# -----------------------

def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def load_system_prompt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().replace("```", "").strip()


def load_tools(path):
    with open(path, "r", encoding="utf-8") as f:
        tools = json.load(f)
    return json.dumps(tools, ensure_ascii=False)


# -----------------------
# THINK HANDLING
# -----------------------

def extract_think(text):
    if not isinstance(text, str):
        return None
    match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    return match.group(1).strip() if match else None


def remove_think(text):
    if not isinstance(text, str):
        return text
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# -----------------------
# FILTER (ADVANCED SCORE)
# -----------------------

def has_tool_error(messages):
    for m in messages:
        if "Error executing tool" in str(m.get("content", "")):
            return True
    return False


def is_advanced_correct(sample):
    score = sample.get("score", {})
    if not score:
        return False

    return (
        score.get("total_score", 0) == 1
        and score.get("num_tool_calls", 999) <= 10
        and not has_tool_error(sample.get("messages", []))

    )
    #         and not has_tool_error(sample.get("messages", []))

# -----------------------
# CONVERSION
# -----------------------

def convert_sample(sample, system_prompt, tools_str):
    conversations = []

    for msg in sample.get("messages", []):
        role = msg.get("role")

        if role == "user":
            conversations.append({
                "from": "human",
                "value": msg.get("content", "")
            })

        elif role == "assistant":
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            thought = extract_think(content)

            if tool_calls:
                for call in tool_calls:
                    fn = call["function"]["name"]
                    args = call["function"]["arguments"]

                    call_json = json.dumps({
                        "name": fn,
                        "arguments": json.loads(args) if isinstance(args, str) else args
                    }, ensure_ascii=False)

                    if thought:
                        value = f"<think>\n{thought}\n</think>\n\n{call_json}"
                    else:
                        value = call_json

                    conversations.append({
                        "from": "function_call",
                        "value": value
                    })

            else:
                conversations.append({
                    "from": "gpt",
                    "value": remove_think(content)
                })

        elif role == "tool":
            conversations.append({
                "from": "observation",
                "value": msg.get("content", "")
            })

    return conversations


# -----------------------
# MAIN PIPELINE
# -----------------------
import random
def convert_file(input_path, output_path, system_md_path, tools_path):
    system_prompt = load_system_prompt(system_md_path)
    tools_str = load_tools(tools_path)

    data = load_jsonl(input_path)

    kept = 0
    skipped = 0

    corpus = []

    
    for sample in data:

        # 🔥 FILTER HERE
        if not is_advanced_correct(sample):
            skipped += 1
            continue
        try:
            conversations = convert_sample(sample, system_prompt, tools_str)

            output = {
                "id": sample.get("id"),
                "system": system_prompt.replace("{current_time}", "2025-12-31"),
                "conversations": conversations,
                "tools": tools_str,
                # "score": sample.get("score")  # ✅ KEEP SCORE
            }
            corpus.append(output)
            kept += 1

        except Exception as e:
            print(f"Error processing sample id={sample.get('id')}: {e}")
            skipped += 1

        
    
    random.shuffle(corpus)
    with open(output_path, "w", encoding="utf-8") as fout:
        for output in corpus:
            fout.write(json.dumps(output, ensure_ascii=False) + "\n")
                

            

    print(f"✅ Kept (advanced=1): {kept}")
    print(f"❌ Skipped: {skipped}")


# -----------------------
# RUN
# -----------------------


if __name__ == "__main__":
    convert_file(
        input_path="../data/eval_train_results_openrouter_openai_gpt-oss-120b.jsonl",          # your raw data
        output_path="../data/output_sharegpt_clean.jsonl",
        system_md_path="../agent/prompt/text2sql_system_prompt.md",
        tools_path="tools.json"
    )