import json
import re

def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks."""
    if not isinstance(text, str):
        return text
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def convert_sample(sample):
    """
    Convert one OpenAI-style trace sample to ShareGPT format.
    """
    conversations = []
    tools = set()

    for msg in sample.get("messages", []):
        role = msg.get("role")

        # --------------------
        # USER → human
        # --------------------
        if role == "user":
            conversations.append({
                "from": "human",
                "value": msg.get("content", "")
            })

        # --------------------
        # ASSISTANT
        # --------------------
        elif role == "assistant":
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            # Case 1: tool call(s)
            if tool_calls:
                for call in tool_calls:
                    fn = call["function"]["name"]
                    args = call["function"]["arguments"]

                    # track tool name
                    tools.add(fn)

                    conversations.append({
                        "from": "function_call",
                        "value": json.dumps({
                            "name": fn,
                            "arguments": json.loads(args) if isinstance(args, str) else args
                        }, ensure_ascii=False)
                    })

            # Case 2: final answer
            else:
                cleaned = strip_think(content)
                conversations.append({
                    "from": "gpt",
                    "value": cleaned
                })

        # --------------------
        # TOOL → observation
        # --------------------
        elif role == "tool":
            conversations.append({
                "from": "observation",
                "value": msg.get("content", "")
            })

    # Optional: build minimal tool schema (you should replace with real schema)
    tool_list = []
    for name in tools:
        tool_list.append({
            "name": name,
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        })

    return {
        "conversations": conversations,
        "tools": json.dumps(tool_list, ensure_ascii=False)
    }


def convert_file(input_path, output_path):
    """
    Convert JSON or JSONL file.
    """
    outputs = []

    with open(input_path, "r", encoding="utf-8") as f:
        first_char = f.read(1)
        f.seek(0)

        # JSONL
        if first_char != "[":
            for line in f:
                sample = json.loads(line)
                outputs.append(convert_sample(sample))
        else:
            data = json.load(f)
            for sample in data:
                outputs.append(convert_sample(sample))

    # write JSONL
    with open(output_path, "w", encoding="utf-8") as f:
        for item in outputs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    convert_file("input.jsonl", "output_sharegpt.jsonl")